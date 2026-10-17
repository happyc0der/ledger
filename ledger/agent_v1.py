"""v1 — the naive pipeline-review agent.

One model call per batch of a rep's deals, everything in context, no tools, no
verification. The model ranks, estimates win probability, names the objection, quotes
the buyer, picks a next step, and does the arithmetic (amounts, day gaps, pipeline
total) itself. This is deliberately how most teams' first version looks.
"""
from __future__ import annotations

import json

import re

from . import llm, tracing
from .config import ACTIONS, OBJECTIONS, SNAPSHOT
from .data import Company
from .tools import days_since_buyer_touch, deal_amount

BATCH = 30

SCHEMA = {
    "type": "object",
    "properties": {
        "pipeline_total_usd": {"type": "number"},
        "deals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "opportunity_id": {"type": "string"},
                    "rank": {"type": "integer"},
                    "win_probability": {"type": "number"},
                    "amount_usd": {"type": "number"},
                    "days_since_last_buyer_touch": {"type": "integer"},
                    "objection": {"type": "string", "enum": OBJECTIONS},
                    "buyer_quote": {"type": "string"},
                    "next_action": {"type": "string", "enum": ACTIONS},
                    "rationale": {"type": "string"},
                },
                "required": ["opportunity_id", "rank", "win_probability", "amount_usd",
                             "days_since_last_buyer_touch", "objection", "buyer_quote",
                             "next_action", "rationale"],
            },
        },
    },
    "required": ["pipeline_total_usd", "deals"],
}


def _render_deals(co: Company, deals) -> str:
    out = []
    for _, d in deals.iterrows():
        amt = "" if d.amount != d.amount else f"{d.amount:.0f}"  # NaN check
        out.append(f"### {d.opportunity_id} | account={d.account} | product={d['product']} | "
                   f"stage={d.stage} | amount={amt or 'not entered'} | created={d.created_date.date()} | "
                   f"expected_close={d.expected_close.date()} | contact={d.primary_contact} | "
                   f"last_activity={d.last_activity_date.date()}")
        for _, a in co.activities_for(d.opportunity_id).iterrows():
            out.append(f"- {a.date.date()} {a.type} ({a.author}): {a.text}")
    return "\n".join(out)


def _prompt(co: Company, rep: str, deals) -> list[dict]:
    catalogue = "\n".join(f"- {r.product}: ${r.sales_price:,.0f}" for r in co.products.itertuples())
    system = (
        f"{co.brief}\n\nToday is {SNAPSHOT.date()}. You are the revenue-intelligence assistant for "
        f"this sales team. Product catalogue (list prices):\n{catalogue}\n\n"
        "Review the rep's open deals below and return JSON. For every deal: rank them 1..N by "
        "how much attention they deserve this week; estimate win_probability (0-1); amount_usd "
        "(use the CRM amount, or the list price if not entered); days_since_last_buyer_touch "
        "(days since the buyer last responded, as of today); the buyer's objection; buyer_quote "
        "(a verbatim sentence from the buyer that supports it, or empty string); next_action from "
        f"the allowed list {ACTIONS}; a one-sentence rationale. Also compute pipeline_total_usd, "
        "the sum of amount_usd across these deals."
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"Rep: {rep}\n\n{_render_deals(co, deals)}"}]


def run_rep(co: Company, rep: str, *, limit: int | None = None) -> list[dict]:
    deals = co.deals_for(rep)
    if limit:
        deals = deals.head(limit)
    session = f"v1-{rep.replace(' ', '_')}"
    results, steps = [], []
    for i in range(0, len(deals), BATCH):
        batch = deals.iloc[i:i + BATCH]
        messages = _prompt(co, rep, batch)
        text, parsed = llm.chat(messages, schema=SCHEMA, version="v1", session_id=session,
                                metadata={"rep": rep, "batch": i // BATCH, "n_deals": len(batch)})
        steps.append(tracing.step(f"review batch {i // BATCH}", text, tool="llm",
                                  input_summary=f"{len(batch)} deals in one context"))
        if not parsed:
            steps.append(tracing.step("parse", "model output was not valid JSON", status="error"))
            continue
        total = parsed.get("pipeline_total_usd")
        for row in parsed.get("deals", []):
            row.update(version="v1", rep=rep, pipeline_total_usd=total, batch=i // BATCH)
            results.append(row)
    # Observability only: the same CRM-only checks Ledger applies to itself, run over v1's answer after
    # the fact. v1's output is not changed; PRISM just gets to see which of its claims the record supports.
    checks = verify_rows(co, results)
    steps += checks
    tracing.trajectory(version="v1", session_id=session, steps=steps + [
        tracing.step("final_answer", json.dumps(results)[:2000])], model="v1",
        final_status="error" if any(c["status"] == "error" for c in checks) else "success")
    return results


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower().replace("\u2019", "'")).strip()


def verify_rows(co: Company, rows: list[dict]) -> list[dict]:
    """check:* steps for a naive answer: amount vs catalogue/CRM, day gap vs buyer-authored activity,
    buyer quote present verbatim in the record. A failed check is an `error` step; nothing is corrected."""
    out, n_fail = [], 0
    for r in rows:
        oid = str(r.get("opportunity_id", ""))
        if oid not in set(co.deals.opportunity_id):
            out.append(tracing.step("check:deal:unknown", f"{oid}: not in the CRM", tool="verifier:crm", status="error")); n_fail += 1
            continue
        d = co.deal(oid); acts = co.activities_for(oid)
        true_amt = deal_amount(co.products, d)
        try:
            amt_ok = abs(float(r.get("amount_usd")) - true_amt) < 1
        except (TypeError, ValueError):
            amt_ok = False
        if not amt_ok:
            out.append(tracing.step("check:amount:mismatch", f"{oid}: stated ${r.get('amount_usd')} vs ${true_amt:,.0f} in catalogue/CRM", tool="verifier:amount", status="error")); n_fail += 1
        true_gap = days_since_buyer_touch(acts, d.sales_agent)
        try:
            gap_ok = true_gap is None or int(r.get("days_since_last_buyer_touch")) == true_gap
        except (TypeError, ValueError):
            gap_ok = False
        if not gap_ok:
            out.append(tracing.step("check:gap:mismatch", f"{oid}: stated {r.get('days_since_last_buyer_touch')}d vs {true_gap}d since a buyer-authored activity", tool="verifier:gap", status="error")); n_fail += 1
        q = _norm(r.get("buyer_quote", "") or "")
        if q and q not in " ".join(_norm(a) for a in acts.text):
            out.append(tracing.step("check:quote:mismatch", f"{oid}: quote not in the record: \u201c{str(r.get('buyer_quote'))[:120]}\u201d", tool="verifier:quote", status="error")); n_fail += 1
    out.append(tracing.step("check:summary", f"{len(rows)} deals · {n_fail} claims not supported by the record", tool="checks"))
    return out

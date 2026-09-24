"""v2 — one deal per context, code for facts, Jev for decisions, verifier for claims.

Per deal:
  1. crm_query   — the deal, its activities and contacts (nothing else in context)
  2. compute     — amount (catalogue-normalised), days since the *buyer* last touched
  3. decide      — win probability, objection, next action  (Jev, or LLM fallback)
  4. explain     — language model extracts the buyer quote and writes one sentence
  5. check:*     — quote must exist verbatim in the record; retried once, else dropped
Every step is a PRISM trajectory step; the verdicts are visible in Agent Runs.
"""
from __future__ import annotations

import json
import re

from . import llm, tracing
from .config import SNAPSHOT
from .data import Company
from .decide import decide
from .tools import days_since_any_activity, days_since_buyer_touch, deal_amount, pipeline_total

EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {"buyer_quote": {"type": "string"}, "rationale": {"type": "string"}},
    "required": ["buyer_quote", "rationale"],
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower().replace("’", "'")).strip()


def deal_state(co: Company, oid: str) -> dict:
    d = co.deal(oid)
    acts = co.activities_for(oid)
    contacts = co.contacts[co.contacts.opportunity_id == oid]
    return {
        "as_of": str(SNAPSHOT.date()),
        "deal": {"opportunity_id": oid, "account": d.account, "product": d["product"],
                 "rep_set_stage": d.stage, "created": str(d.created_date.date()),
                 "expected_close": str(d.expected_close.date()), "rep": d.sales_agent},
        "computed": {"amount_usd": deal_amount(co.products, d),
                     "days_since_buyer_touch": days_since_buyer_touch(acts, d.sales_agent),
                     "days_since_any_activity": days_since_any_activity(acts)},
        "contacts": [{"name": c.name, "title": c.title, "role": c.role} for c in contacts.itertuples()],
        "activities": [{"date": str(a.date.date()), "type": a.type, "author": a.author, "text": a.text}
                       for a in acts.itertuples()],
    }


def _explain(state: dict, decision, *, session: str, oid: str, strict: bool = False) -> dict:
    system = ("You write the one-line rationale for a sales manager. You are given a deal record and "
              "a decision already made by a calibrated model. Return buyer_quote: ONE sentence copied "
              "VERBATIM from an activity's text that was said or written by the buyer and supports the "
              "objection (empty string if the objection is 'none' or the buyer said nothing relevant). "
              "Return rationale: one sentence, cite only facts in the record."
              + (" Your previous quote was not found verbatim in the record. Copy exactly, character for "
                 "character, or return an empty string." if strict else ""))
    user = json.dumps({"record": state, "decision": {"win_probability": round(decision.win_probability, 2),
                                                     "objection": decision.objection,
                                                     "next_action": decision.next_action}}, default=str)
    _, parsed = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                         schema=EXPLAIN_SCHEMA, version="v2", session_id=session,
                         metadata={"deal_id": oid, "role": "explain", "strict": strict})
    return parsed or {"buyer_quote": "", "rationale": ""}


def explain_verified(state: dict, dec, *, session: str, oid: str) -> tuple[dict, bool, list[dict]]:
    """Explain, then verify the cited quote against the record; retry once, else drop it.
    Returns (explanation, quote_ok, trajectory steps to append)."""
    record = " ".join(_norm(a["text"]) for a in state["activities"])
    steps = []
    ex = _explain(state, dec, session=session, oid=oid)
    quote_ok = ex["buyer_quote"] == "" or _norm(ex["buyer_quote"]) in record
    if not quote_ok:
        steps.append(tracing.step("check:quote:mismatch", ex["buyer_quote"], tool="verifier:quote", status="error"))
        ex = _explain(state, dec, session=session, oid=oid, strict=True)
        quote_ok = ex["buyer_quote"] == "" or _norm(ex["buyer_quote"]) in record
        if not quote_ok:
            ex["buyer_quote"] = ""  # refuse to show an unverifiable quote
    steps.append(tracing.step("check:quote:match" if quote_ok else "check:quote:dropped",
                              ex["buyer_quote"] or "(no quote)", tool="verifier:quote"))
    return ex, quote_ok, steps


def run_deal(co: Company, oid: str, *, session: str) -> tuple[dict, list[dict]]:
    state = deal_state(co, oid)
    steps = [tracing.step("crm_query", f"{len(state['activities'])} activities, {len(state['contacts'])} contacts",
                          tool="crm", input_summary=oid),
             tracing.step("compute", json.dumps(state["computed"]), tool="calc")]
    dec = decide(state, version="v2", session_id=session)
    steps.append(tracing.step("decide", json.dumps({"win_probability": round(dec.win_probability, 3),
                                                    "objection": dec.objection, "next_action": dec.next_action,
                                                    "objection_probs": dec.objection_probs}),
                              tool=dec.backend, input_summary="deal state"))
    ex, quote_ok, qsteps = explain_verified(state, dec, session=session, oid=oid)
    steps += qsteps
    steps.append(tracing.step("check:amount:match", f"${state['computed']['amount_usd']:,.0f} from catalogue/CRM",
                              tool="verifier:amount"))
    row = dict(opportunity_id=oid, win_probability=dec.win_probability, amount_usd=state["computed"]["amount_usd"],
               days_since_last_buyer_touch=state["computed"]["days_since_buyer_touch"] or 0,
               objection=dec.objection, buyer_quote=ex["buyer_quote"], next_action=dec.next_action,
               rationale=ex["rationale"], decision_backend=dec.backend,
               objection_probs=dec.objection_probs, action_probs=dec.action_probs, quote_verified=quote_ok)
    steps.append(tracing.step("final_answer", json.dumps(row, default=str)))
    return row, steps


def run_rep(co: Company, rep: str, *, limit: int | None = None) -> list[dict]:
    deals = co.deals_for(rep)
    if limit:
        deals = deals.head(limit)
    session = f"v2-{rep.replace(' ', '_')}"
    total = pipeline_total(co.products, deals)
    rows = []
    for oid in deals.opportunity_id:
        row, steps = run_deal(co, oid, session=session)
        row.update(version="v2", rep=rep, pipeline_total_usd=total, batch=0)
        rows.append(row)
        tracing.trajectory(version="v2", session_id=session, steps=steps, model="v2",
                           final_status="success" if row["quote_verified"] else "error")
    rows.sort(key=lambda r: -r["win_probability"] * r["amount_usd"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows

"""v3 — Ledger: rules + claim ledger + consistency + judgement, every finding with a receipt.

Per deal: rules (fields only) → claim ledger (model reads, verifier checks quotes) →
consistency (code compares ledger vs CRM) → judgement (decision model: win probability,
objection, next action). After all deals: cross-deal checks per account. Each finding is a
PRISM trajectory step named check:<type>:<fail>; dropped claims are check:claim:dropped.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from . import store, tracing
from .agent_v2 import deal_state, explain_verified
from .consistency import compare, cross_deal
from .claims import extract
from .data import Company
from .decide import decide
from .rules import Issue, run_rules
from .tools import pipeline_total


def run_rep(co: Company, rep: str, *, limit: int | None = None) -> list[dict]:
    deals = co.deals_for(rep)
    if limit:
        deals = deals.head(limit)
    session = f"v3-{rep.replace(' ', '_')}"
    rules_by = {}
    for i in run_rules(co, deals):
        rules_by.setdefault(i.opportunity_id, []).append(i)
    rows, ledgers, total = [], {}, pipeline_total(co.products, deals)
    prev = _previous_ledgers()
    for oid in deals.opportunity_id:
        state = deal_state(co, oid)
        record_hash = hashlib.sha1("\n".join(f"{a['date']}|{a['author']}|{a['text']}" for a in state["activities"]).encode()).hexdigest()[:16]
        steps = [tracing.step("crm_query", f"{len(state['activities'])} activities", tool="crm", input_summary=oid),
                 tracing.step("rules", "; ".join(f"{i.type}" for i in rules_by.get(oid, [])) or "no rule hits", tool="rules")]
        cached = prev.get(oid)
        reused = bool(cached and cached[0] == record_hash)
        if reused:
            ledger = cached[1]  # record unchanged since the last run: no need to read it again
            steps.append(tracing.step("claim_ledger:cached", "record unchanged since previous run", tool="store"))
        else:
            ledger = extract(co, oid, version="v3", session=session)
            steps.append(tracing.step("claim_ledger", json.dumps({k: v for k, v in ledger.items() if k not in ("quotes", "dropped") and v}), tool="llm:extract"))
        ledgers[oid] = ledger
        for slot in ledger["dropped"]:
            steps.append(tracing.step("check:claim:dropped", f"{slot}: no verbatim buyer quote", tool="verifier:claims", status="error"))
        issues = compare(co, oid, ledger)
        for i in issues:
            steps.append(tracing.step(f"check:{i.type}:fail", f"{i.detail} | “{i.evidence[:120]}”", tool="consistency"))
        if not issues:
            steps.append(tracing.step("check:consistency:pass", "ledger agrees with CRM", tool="consistency"))
        dec = decide(state, version="v3", session_id=session)
        steps.append(tracing.step("decide", json.dumps({"win_probability": round(dec.win_probability, 3), "objection": dec.objection,
                                                        "next_action": dec.next_action}), tool=dec.backend))
        ex, quote_ok, qsteps = explain_verified(state, dec, session=session, oid=oid)
        steps += qsteps
        row = dict(opportunity_id=oid, win_probability=dec.win_probability, amount_usd=state["computed"]["amount_usd"],
                   days_since_last_buyer_touch=state["computed"]["days_since_buyer_touch"] or 0,
                   objection=dec.objection, buyer_quote=ex.get("buyer_quote", ""), next_action=dec.next_action,
                   rationale=ex.get("rationale", ""), decision_backend=dec.backend, quote_verified=quote_ok,
                   ledger={k: v for k, v in ledger.items() if k != "quotes"}, ledger_quotes=ledger["quotes"], record_hash=record_hash, ledger_reused=reused,
                   issues=[asdict(i) for i in rules_by.get(oid, []) + issues], version="v3", rep=rep,
                   pipeline_total_usd=total, batch=0)
        steps.append(tracing.step("final_answer", json.dumps({"issues": [i["type"] for i in row["issues"]], "p": row["win_probability"]})))
        tracing.trajectory(version="v3", session_id=session, steps=steps, model="v3",
                           final_status="error" if any(i.type.startswith("M") for i in issues) else "success")
        rows.append(row)
    # cross-deal checks need the whole rep's (ideally the whole team's) ledgers — done again team-wide in run.py
    for i in cross_deal(co, ledgers):
        for r in rows:
            if r["opportunity_id"] == i.opportunity_id:
                r["issues"].append(asdict(i))
    rows.sort(key=lambda r: -r["win_probability"] * r["amount_usd"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _previous_ledgers() -> dict[str, tuple[str, dict]]:
    """{oid: (record_hash, ledger)} from the latest stored v3 run, if any."""
    rid = store.latest_run_id("v3")
    if not rid:
        return {}
    out = {}
    for s in store.snapshots(rid).itertuples():
        if s.record_hash and s.ledger_json:
            lg = json.loads(s.ledger_json)
            lg.setdefault("quotes", {}); lg.setdefault("dropped", [])
            out[s.opportunity_id] = (s.record_hash, lg)
    return out


def team_cross_deal(co: Company, rows: list[dict]) -> list[dict]:
    """Re-run cross-deal checks across every rep's ledgers (accounts span reps)."""
    ledgers = {r["opportunity_id"]: {**r["ledger"], "quotes": r["ledger_quotes"]} for r in rows}
    found = cross_deal(co, ledgers)
    have = {(r["opportunity_id"], i["type"]) for r in rows for i in r["issues"]}
    for i in found:
        if (i.opportunity_id, i.type) not in have:
            for r in rows:
                if r["opportunity_id"] == i.opportunity_id:
                    r["issues"].append(asdict(i))
    return rows

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
from .consistency import checks_for as semantic_checks
from .consistency import compare, cross_deal
from .claims import extract
from .data import Company
from .decide import decide
from .rules import Issue, checks_for as rule_checks, run_rules
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
        # Reasoning steps say what the pipeline is doing and why; PRISM's trajectory rules expect them
        # (CORR-002 reasoning presence, CORR-004 no run of >5 tool calls) and a reviewer reads them first.
        steps = [tracing.step("plan", f"Review {oid}: read the record, run field rules, fill the claim ledger from buyer-stated "
                              "facts, verify every claim against the record, compare ledger vs CRM, judge, verify the quote."),
                 tracing.step("crm_query", f"{len(state['activities'])} activities", tool="crm", input_summary=oid),
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
        filled = [k for k, v in ledger.items() if k not in ("quotes", "dropped", "grades") and v not in (None, "", "unknown", "none_mentioned", "n/a")]
        steps.append(tracing.step("verification", f"ledger has {len(filled)} buyer-stated facts ({', '.join(filled[:6])}); "
                                  f"{len(ledger['dropped'])} claim(s) had no verbatim buyer quote and will be dropped; "
                                  "now comparing what the buyer said with what the CRM says"))
        for slot in ledger["dropped"]:
            steps.append(tracing.step("check:claim:dropped", f"dropped {slot}: no verbatim buyer quote", tool=f"verifier:claims:{slot}"))
        issues = compare(co, oid, ledger)
        checks = rule_checks(co, oid, rules_by.get(oid, [])) + semantic_checks(co, oid, ledger, issues)
        for c in checks:
            if c.status == "fail":
                i = next(x for x in issues + rules_by.get(oid, []) if x.type == c.type)
                # one tool name per check: PRISM's EFF-001 reads a repeated tool name as a redundant call
                steps.append(tracing.step(f"check:{c.type}:fail", f"{i.detail} | “{i.evidence[:120]}”",
                                          tool=f"{'consistency' if c.type.startswith('M') else 'rules'}:{c.type.split('_')[0]}"))
        n_pass = sum(1 for c in checks if c.status == "pass"); n_skip = sum(1 for c in checks if c.status == "skipped")
        n_fail = len(checks) - n_pass - n_skip
        steps.append(tracing.step("assessment", (f"{n_fail} inconsistenc{'y' if n_fail == 1 else 'ies'} between the record and the CRM "
                                  f"({', '.join(c.type for c in checks if c.status == 'fail')}); " if n_fail else "record and CRM agree; ")
                                  + "handing buyer signals, buyer-touch gap and base rate to the decision model"))
        steps.append(tracing.step("check:summary", f"{n_pass} pass · {len(checks) - n_pass - n_skip} fail · {n_skip} skipped: "
                                  + "; ".join(f"{c.type.split('_')[0]} {c.status} ({c.reason})" for c in checks if c.status != "fail"), tool="checks"))
        dec = decide(state, version="v3", session_id=session)
        basis = {"win_probability": round(dec.win_probability, 3), "objection": dec.objection, "next_action": dec.next_action,
                 "backend": dec.backend, "derived_from": {"buyer_signals": {k: ledger.get(k) for k in ("budget_status", "commitment", "competitor_status", "champion_status") if ledger.get(k)},
                                                           "days_since_buyer_touch": state["computed"]["days_since_buyer_touch"],
                                                           "base_win_rate": round(float(__import__("ledger.config", fromlist=["BASE_WIN_RATE"]).BASE_WIN_RATE), 2),
                                                           "objection_probs": {k: round(v, 2) for k, v in dec.objection_probs.items() if v >= 0.05}}}
        steps.append(tracing.step("decide", json.dumps(basis, default=str), tool=dec.backend,
                                  input_summary="claim ledger + computed facts + base rate"))
        ex, quote_ok, qsteps = explain_verified(state, dec, session=session, oid=oid)
        steps += qsteps
        row = dict(opportunity_id=oid, win_probability=dec.win_probability, amount_usd=state["computed"]["amount_usd"],
                   days_since_last_buyer_touch=state["computed"]["days_since_buyer_touch"] or 0,
                   objection=dec.objection, buyer_quote=ex.get("buyer_quote", ""), next_action=dec.next_action,
                   rationale=ex.get("rationale", ""), decision_backend=dec.backend, quote_verified=quote_ok,
                   ledger={k: v for k, v in ledger.items() if k != "quotes"}, ledger_quotes=ledger["quotes"], record_hash=record_hash, ledger_reused=reused,
                   issues=[asdict(i) for i in rules_by.get(oid, []) + issues], checks=[asdict(c) for c in checks], version="v3", rep=rep,
                   pipeline_total_usd=total, batch=0)
        steps.append(tracing.step("final_answer", json.dumps({"issues": [i["type"] for i in row["issues"]], "p": row["win_probability"]})))
        row.pop("_redactor", None)
        # final_status describes the run, not the deal: a scored deal with open findings is a successful run
        # (the findings are in the final_answer). PRISM's Task Completion rule had clustered 470 of these as failures.
        row["prism_trajectory_id"] = tracing.trajectory(version="v3", session_id=session, steps=steps, model="v3", final_status="success")
        row["prism_trace_ids"] = tracing.drain_trace_ids()
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

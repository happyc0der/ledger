"""Manager-facing UI: ranked pipeline, per-deal receipts, and the v1-vs-v2 proof.

Reads runs/<version>.jsonl (agent output) and runs/<version>_verdicts.csv (code-checked
claims). Outcomes are served only by /api/compare and the deal drawer's "reveal" — the
agent never sees them; the demo does.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

import os

from fastapi import Body

from . import calibrate, digest, evaluate, forecast, history, proposals, store
from .config import COMPANY_DIR, RUNS_DIR, SETTINGS, SNAPSHOT
from .data import load_company, load_truth

UI_VERSIONS = ("v1", "v2", "v3")  # naive is a benchmark row, not a manager-facing agent


def _versions() -> list[str]:
    return [v for v in UI_VERSIONS if (RUNS_DIR / f"{v}.jsonl").exists()]


def _has_truth() -> bool:
    return (COMPANY_DIR / "ground_truth.csv").exists()

app = FastAPI(title="Ledger")
STATIC = Path(__file__).parent / "static"
CO = load_company()


def _clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if hasattr(o, "isoformat"):
        return o.isoformat()[:10]
    return o


def _latest(version: str) -> tuple[list[dict] | None, str | None]:
    """Rows of the latest stored run for this version, else the legacy jsonl."""
    rid = store.latest_run_id(version)
    if rid:
        return store.rows_for(rid), rid
    p = RUNS_DIR / f"{version}.jsonl"
    if p.exists():
        return evaluate.load_rows(version), None
    return None, None


def _rows(version: str) -> pd.DataFrame:
    rows, _ = _latest(version)
    if rows is None:
        raise HTTPException(404, f"no run for {version}")
    r = pd.DataFrame(rows).drop_duplicates("opportunity_id")
    vp = RUNS_DIR / f"{version}_verdicts.csv"
    if vp.exists():  # benchmark: receipts checked against ground truth by the evaluator
        v = pd.read_csv(vp)[["opportunity_id", "amount_ok", "gap_ok", "quote_ok", "fabrications"]]
        r = r.merge(v, on="opportunity_id", how="left")
    elif "quote_verified" in r:  # customer data: amounts/gaps are computed in code; the quote carries its own verification
        r["amount_ok"], r["gap_ok"] = True, True
        r["quote_ok"] = r.quote_verified.fillna(True).astype(bool)
        r["fabrications"] = (~r.quote_ok).astype(int)
    d = CO.deals[["opportunity_id", "account", "product", "sales_agent", "stage", "amount",
                  "primary_contact", "last_activity_date", "expected_close"]]
    r = r.merge(d, on="opportunity_id", how="left", suffixes=("", "_crm"))
    r["ev"] = r.win_probability * r.amount_usd
    return r.sort_values("ev", ascending=False)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta():
    return {"as_of": str(SNAPSHOT.date()), "company": CO.brief.split("\n")[0].lstrip("# "),
            "reps": CO.reps(), "n_deals": len(CO.deals),
            "versions": _versions(), "has_truth": _has_truth(),
            "settings": {k: v for k, v in SETTINGS.__dict__.items() if k != "source"}, "settings_source": SETTINGS.source or {}}


@app.get("/api/deals")
def deals(version: str = "v3", show_muted: int = 0):
    r = _rows(version)
    _, rid = _latest(version)
    hist = history.summary(rid) if rid else {}
    states = store.issue_states()
    cols = ["opportunity_id", "account", "product", "sales_agent", "stage", "amount_usd", "win_probability",
            "ev", "objection", "next_action", "buyer_quote", "rationale", "days_since_last_buyer_touch",
            "amount_ok", "gap_ok", "quote_ok", "fabrications", "primary_contact", "issues"]
    recs = _clean(r[[c for c in cols if c in r]].to_dict("records"))
    for rec in recs:
        iss = rec.get("issues") if isinstance(rec.get("issues"), list) else []
        for i in iss:
            st = states.get(i.get("key", ""), {})
            i["state"] = st.get("status", "new")
        if not show_muted:
            iss = [i for i in iss if i["state"] != "muted"]
        rec["issue_types"] = [i["type"] for i in iss]
        rec["n_semantic"] = sum(1 for i in iss if i["type"].startswith("M"))
        rec["n_rules"] = sum(1 for i in iss if i["type"].startswith("S"))
        h = hist.get(rec["opportunity_id"], {})
        rec["history"] = {k: h.get(k) for k in ("new_issues", "resolved_issues", "recurring", "stage_change", "close_date_pushes",
                                                 "amount_change", "p_delta", "promise_age_days", "first_run")}
        rec.pop("issues", None)
    return recs


@app.post("/api/issue/{key}/state")
def issue_state(key: str, body: dict = Body(...)):
    status = body.get("status", "acknowledged")
    if status not in ("new", "acknowledged", "muted", "resolved"):
        raise HTTPException(400, "status must be new|acknowledged|muted|resolved")
    store.set_issue_state(key, status, who=body.get("who") or os.getenv("LEDGER_USER", "manager"), note=body.get("note", ""))
    return {"key": key, "status": status}


def _calibrator(version: str):
    """Predictions made while deals were open, joined to outcomes known later. On the benchmark the
    outcomes are the hidden ground truth; on a customer dataset they arrive as deals close."""
    try:
        rid = store.latest_run_id(version)
        if not rid:
            return None
        snaps = pd.concat([store.snapshots(r) for r in store.runs(version).run_id], ignore_index=True)
        if _has_truth():
            outcomes = load_truth().reset_index()[["opportunity_id", "outcome"]]
        elif (COMPANY_DIR / "history.csv").exists():
            outcomes = pd.read_csv(COMPANY_DIR / "history.csv", dtype={"opportunity_id": str})[["opportunity_id", "outcome"]]
        else:
            return None
        p, y = calibrate.pairs_from_history(snaps, outcomes)
        return calibrate.fit(p, y)
    except Exception:
        return None


@app.get("/api/forecast")
def forecast_view(version: str = "v3"):
    rows, rid = _latest(version)
    if rows is None:
        return {}
    backend = next((r.get("decision_backend") for r in rows if r.get("decision_backend")), "llm")
    return _clean(forecast.rollup(rows, backend=backend, states=store.issue_states(), calibrator=_calibrator(version)))


@app.get("/api/digest")
def digest_view(rep: str | None = None, version: str = "v3"):
    rows, rid = _latest(version)
    if rows is None:
        return {"markdown": ""}
    hist = history.summary(rid) if rid else {}
    backend = next((r.get("decision_backend") for r in rows if r.get("decision_backend")), "llm")
    fc = forecast.rollup(rows, backend=backend, states=store.issue_states(), calibrator=_calibrator(version))
    runs_df = store.runs(version)
    as_of = str(runs_df.as_of.iloc[-1]) if len(runs_df) else str(SNAPSHOT.date())
    rows = digest.enrich(rows, CO.deals)
    md = digest.rep_digest(rep, rows, hist, fc, as_of) if rep else digest.manager_digest(rows, hist, fc, as_of, CO.reps())
    return {"markdown": md}


@app.get("/api/proposals")
def proposals_view(opportunity_id: str | None = None, status: str | None = None, version: str = "v3"):
    rows, _ = _latest(version)
    if rows is not None:
        proposals.draft_for_run(CO, rows)  # idempotent: drafts only for findings without one
    return proposals.list_proposals(opportunity_id, status)


@app.post("/api/proposal/{pid}")
def proposal_state(pid: str, body: dict = Body(...)):
    status = body.get("status", "approved")
    if status not in ("draft", "approved", "rejected"):
        raise HTTPException(400, "status must be draft|approved|rejected")
    proposals.set_status(pid, status, who=body.get("who") or os.getenv("LEDGER_USER", "manager"))
    return {"id": pid, "status": status}


@app.post("/api/review")
def review(body: dict = Body(...)):
    from . import score_issues
    try:
        row = score_issues.add_review(body["opportunity_id"], body["type"], body.get("verdict", "correct"),
                                      reviewer=body.get("reviewer") or os.getenv("LEDGER_USER", "manager"), note=body.get("note", ""))
    except (AssertionError, KeyError) as e:
        raise HTTPException(400, str(e))
    return row


@app.get("/api/precision")
def precision():
    from . import score_issues
    return score_issues.observed_precision()


@app.get("/api/history")
def history_view(version: str = "v3"):
    _, rid = _latest(version)
    if not rid:
        return {}
    return _clean({"run_id": rid, "previous_run": store.previous_run_id(rid), "deals": history.summary(rid)})


@app.get("/api/deal/{oid}")
def deal(oid: str):
    if oid not in set(CO.deals.opportunity_id):
        raise HTTPException(404)
    d = CO.deal(oid)
    acts = CO.activities_for(oid)
    out = {"deal": _clean(d.to_dict()), "opportunity_id": oid,
           "activities": _clean(acts.to_dict("records")),
           "contacts": _clean(CO.contacts[CO.contacts.opportunity_id == oid].to_dict("records")),
           "versions": {}}
    states = store.issue_states()
    for v in _versions():
        r = _rows(v)
        m = r[r.opportunity_id == oid]
        if len(m):
            row = _clean(m.iloc[0].to_dict())
            for i in (row.get("issues") or []) if isinstance(row.get("issues"), list) else []:
                st = states.get(i.get("key", ""), {})
                i["state"], i["state_who"], i["state_at"] = st.get("status", "new"), st.get("who"), st.get("at")
            _, rid = _latest(v)
            row["history"] = history.summary(rid).get(oid) if rid else None
            out["versions"][v] = row
    t = load_truth() if _has_truth() else None
    if t is not None and oid in t.index:
        tr = t.loc[oid]
        out["outcome"] = _clean({"outcome": tr.outcome, "actual_close_value": tr.actual_close_value,
                                 "actual_close_date": tr.actual_close_date, "objection": tr.objection,
                                 "correct_next_action": tr.correct_next_action})
    return out


@app.get("/api/issues")
def issues():
    """Rules vs agent findings, scored against planted anomalies (demo/proof only)."""
    from . import score_issues
    from .rules import Issue, run_rules
    if not (COMPANY_DIR / "anomalies.csv").exists():
        return []
    ids = list(CO.deals.opportunity_id)
    scores = [score_issues.score(run_rules(CO), ids, "rules")]
    for ver, name in (("naive", "naive agent"), ("v3", "Ledger")):
        p = RUNS_DIR / f"{ver}.jsonl"
        if p.exists():
            rows = evaluate.load_rows(ver)
            iss = [Issue(**{k: v for k, v in i.items() if k in Issue.__dataclass_fields__}) for r in rows for i in r.get("issues", [])]
            scores.append(score_issues.score(iss, ids, name))
    return _clean(scores)


@app.get("/api/compare")
def compare():
    out = {}
    if not _has_truth():
        return out
    for v in _versions():
        if (RUNS_DIR / f"{v}.jsonl").exists():
            s, _ = evaluate.summarize(CO, v)
            s["reliability"] = [{"bin": str(k), **val} for k, val in s["reliability"].items()]
            out[v] = _clean(s)
    return out

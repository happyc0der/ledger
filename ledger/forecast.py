"""Forecast roll-up a manager can defend: commit and best case are built only from deals the
agent has no open semantic issue with, and the numbers say how far they can be trusted."""
from __future__ import annotations

from .config import SETTINGS
from .rules import LATE


def rollup(rows: list[dict], *, backend: str = "llm", states: dict | None = None) -> dict:
    states = states or {}
    per_rep: dict[str, dict] = {}
    excluded = []
    for r in rows:
        rep = r.get("rep", "?")
        p = float(r.get("win_probability") or 0)
        amt = float(r.get("amount_usd") or 0)
        open_issues = [i for i in r.get("issues", []) if states.get(i.get("key", ""), {}).get("status") not in ("muted", "resolved")]
        sem = [i["type"] for i in open_issues if i["type"].startswith("M")]
        s1 = any(i["type"] == "S1_past_close_date" for i in open_issues)
        bucket = per_rep.setdefault(rep, {"pipeline": 0.0, "weighted": 0.0, "commit": 0.0, "best_case": 0.0, "deals": 0, "excluded": 0})
        bucket["pipeline"] += amt; bucket["weighted"] += p * amt; bucket["deals"] += 1
        if p >= SETTINGS.commit_p and not sem and not s1:
            bucket["commit"] += amt
        if p >= SETTINGS.best_case_p and not any(t in ("M1_stage_vs_buyer", "M6_zombie") for t in sem):
            bucket["best_case"] += amt
        if (sem or s1) and p >= SETTINGS.best_case_p:
            bucket["excluded"] += 1
            excluded.append({"opportunity_id": r["opportunity_id"], "rep": rep, "amount": amt, "p": round(p, 2), "why": sorted(set(sem)) + (["S1_past_close_date"] if s1 else [])})
    team = {k: sum(b[k] for b in per_rep.values()) for k in ("pipeline", "weighted", "commit", "best_case")}
    team["deals"] = sum(b["deals"] for b in per_rep.values())
    calibrated = backend == "jev"
    return {"team": team, "per_rep": per_rep, "excluded": excluded,
            "calibration": "calibrated decision model" if calibrated else "uncalibrated fallback — treat bands, not points",
            "commit_p": SETTINGS.commit_p, "best_case_p": SETTINGS.best_case_p}

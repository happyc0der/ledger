"""Monday-morning digests, per rep and per manager. Pure code over the store; no model call."""
from __future__ import annotations

from collections import defaultdict


def _fmt(n):
    return f"${n:,.0f}"


def enrich(rows: list[dict], deals) -> list[dict]:
    """Attach account/product/stage from the CRM frame to run rows (rows only carry the agent's output)."""
    d = deals.set_index("opportunity_id")
    out = []
    for r in rows:
        if r["opportunity_id"] in d.index:
            c = d.loc[r["opportunity_id"]]
            r = {**r, "account": r.get("account") or c.get("account"), "product": r.get("product") or c.get("product"), "stage": r.get("stage") or c.get("stage")}
        out.append({**r, "account": r.get("account") or r["opportunity_id"]})
    return out


def rep_digest(rep: str, rows: list[dict], hist: dict, forecast: dict, as_of: str) -> str:
    mine = [r for r in rows if r.get("rep") == rep]
    by_oid = {r["opportunity_id"]: r for r in mine}
    new, resolved, pushes, promises = [], [], [], []
    for r in mine:
        h = hist.get(r["opportunity_id"], {})
        keys = {i.get("key"): i for i in r.get("issues", [])}
        for k in h.get("new_issues", []):
            if k in keys:
                new.append((r, keys[k]))
        resolved += [(r, k) for k in h.get("resolved_issues", [])]
        if h.get("close_date_pushes"):
            pushes.append((r, h["close_date_pushes"]))
        if h.get("promise_age_days") and h["promise_age_days"] > 14:
            promises.append((r, h["promise_age_days"]))
    f = forecast["per_rep"].get(rep, {})
    md = [f"# {rep} — week of {as_of}", "",
          f"Pipeline {_fmt(f.get('pipeline', 0))} · weighted {_fmt(f.get('weighted', 0))} · commit {_fmt(f.get('commit', 0))} · "
          f"best case {_fmt(f.get('best_case', 0))} ({forecast['calibration']})", ""]
    if new:
        md += ["## New this week", ""] + [f"- **{r['account']}** ({r['opportunity_id']}): {i['type'].replace('_', ' ')} — {i['detail']}"
                                           + (f"\n  > “{i['evidence']}”" if i.get('evidence') else "") + f"\n  → {i.get('action', '')}" for r, i in new] + [""]
    if promises:
        md += ["## Promises past due", ""] + [f"- **{r['account']}**: buyer's last promise is {d} days old" for r, d in promises] + [""]
    if pushes:
        md += ["## Close dates pushed", ""] + [f"- **{r['account']}**: pushed {n}× so far" for r, n in pushes] + [""]
    if resolved:
        md += ["## Resolved since last week", ""] + [f"- **{r['account']}**: {len([k])} issue(s) cleared" for r, k in resolved] + [""]
    ask = [r for r in mine if any(i["type"] in ("M3_expired_promise", "M9_missing_economic_buyer", "M2_contact_contradiction") for i in r.get("issues", []))]
    if ask:
        md += ["## Ask before the review", ""] + [f"- **{r['account']}**: " + "; ".join(sorted({i['action'] for i in r['issues'] if i.get('action')})) for r in ask[:8]] + [""]
    return "\n".join(md)


def manager_digest(rows: list[dict], hist: dict, forecast: dict, as_of: str, reps: list[str]) -> str:
    t = forecast["team"]
    md = [f"# Team — week of {as_of}", "",
          f"Pipeline {_fmt(t['pipeline'])} · weighted {_fmt(t['weighted'])} · **commit {_fmt(t['commit'])}** · best case {_fmt(t['best_case'])} "
          f"({forecast['calibration']}); {len(forecast['excluded'])} deals excluded from commit/best case for open issues", ""]
    counts = defaultdict(lambda: defaultdict(int))
    for r in rows:
        h = hist.get(r["opportunity_id"], {})
        counts[r.get("rep")]["new"] += len(h.get("new_issues", []))
        counts[r.get("rep")]["resolved"] += len(h.get("resolved_issues", []))
        counts[r.get("rep")]["pushes"] += h.get("close_date_pushes", 0) or 0
        counts[r.get("rep")]["open_semantic"] += sum(1 for i in r.get("issues", []) if i["type"].startswith("M"))
    md += ["| rep | open semantic issues | new | resolved | close-date pushes | commit |", "|---|---|---|---|---|---|"]
    for rep in reps:
        c = counts.get(rep, {})
        md.append(f"| {rep} | {c.get('open_semantic', 0)} | {c.get('new', 0)} | {c.get('resolved', 0)} | {c.get('pushes', 0)} | {_fmt(forecast['per_rep'].get(rep, {}).get('commit', 0))} |")
    md += ["", "## Excluded from the forecast", ""] + [f"- {e['rep']} · {e['opportunity_id']} · {_fmt(e['amount'])} at {e['p']:.0%}: {', '.join(e['why'])}" for e in forecast["excluded"][:15]]
    return "\n".join(md)

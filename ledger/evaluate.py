"""Score a version's output against the hidden ground truth. Pure code; no model.

Per-deal verdicts are what v2 writes back into PRISM as check:* steps, so this module
is also the definition of "fabrication" for the whole project.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .config import RUNS_DIR
from .data import Company, load_truth
from .tools import deal_amount, days_since_buyer_touch, pipeline_total

GENERIC = {"re_engage_dormant"}  # the only allowed action that is close to "follow up"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower().replace("’", "'")).strip()


def load_rows(version: str) -> list[dict]:
    """Rows of runs/<dataset>/<version>.jsonl, tolerant of blank lines."""
    return [json.loads(l) for l in (RUNS_DIR / f"{version}.jsonl").read_text().splitlines() if l.strip()]


def load_results(version: str) -> pd.DataFrame:
    return pd.DataFrame(load_rows(version))


def verdicts(co: Company, res: pd.DataFrame) -> pd.DataFrame:
    """One row per deal the agent reported on, with each claim checked against the CRM."""
    truth = load_truth()
    out = []
    for r in res.itertuples():
        oid = r.opportunity_id
        if oid not in truth.index:
            out.append(dict(opportunity_id=oid, unknown_deal=True))
            continue
        t = truth.loc[oid]
        d = co.deal(oid)
        acts = co.activities_for(oid)
        true_amt = deal_amount(co.products, d)
        true_gap = days_since_buyer_touch(acts, d.sales_agent)
        quote = _norm(getattr(r, "buyer_quote", "") or "")
        # Buyer words can sit inside a rep's call note ('Buyer: "..."'), so search the whole record.
        record_text = " ".join(_norm(a) for a in acts.text)
        p = float(r.win_probability)
        won = int(t.outcome == "Won")
        out.append(dict(
            opportunity_id=oid, rep=r.rep, version=r.version,
            won=won, p=p, brier=(p - won) ** 2,
            actual_close_value=float(t.actual_close_value),
            amount_ok=abs(float(r.amount_usd) - true_amt) < 1,
            gap_ok=(true_gap is None) or (int(r.days_since_last_buyer_touch) == true_gap),
            quote_ok=(quote == "") or (quote in record_text),
            quote_given=quote != "",
            objection_ok=r.objection == t.objection,
            action_ok=r.next_action == t.correct_next_action,
            generic_action=r.next_action in GENERIC,
            stage_trap=bool(t.rep_stage_inflated),
        ))
    v = pd.DataFrame(out)
    v["fabrications"] = (~v.amount_ok).astype(int) + (~v.gap_ok).astype(int) + (~v.quote_ok).astype(int)
    return v


def summarize(co: Company, version: str) -> dict:
    raw = load_results(version)
    truth = load_truth()
    # An agent that reports on deals that don't exist, or the same deal twice, is a
    # failure in its own right: count it, then score only the first real mention.
    phantom = int((~raw.opportunity_id.isin(truth.index)).sum())
    duplicates = int(raw.opportunity_id.duplicated().sum())
    res = raw[raw.opportunity_id.isin(truth.index)].drop_duplicates("opportunity_id")
    v = verdicts(co, res)
    # Team-level prioritisation: the manager sees deals ordered by expected value as the agent states it.
    res = res.assign(ev=res.win_probability * res.amount_usd).sort_values("ev", ascending=False)
    top = res.head(20).opportunity_id
    captured = float(truth.loc[top].actual_close_value.sum())
    oracle = float(truth.loc[res.opportunity_id].actual_close_value.nlargest(20).sum())
    # Pipeline total as stated by the agent (sum over batches) vs computed from the CRM.
    stated_total = float(res.groupby(["rep", "batch"]).pipeline_total_usd.first().sum())
    true_total = pipeline_total(co.products, co.deals[co.deals.opportunity_id.isin(res.opportunity_id)])
    bins = pd.cut(v.p, [0, .2, .4, .6, .8, 1.0], include_lowest=True)
    rel = v.groupby(bins, observed=True).agg(n=("won", "size"), stated=("p", "mean"), actual=("won", "mean"))
    return dict(
        version=version, deals=len(v), coverage=len(v) / len(co.deals),
        phantom_deals=phantom, duplicate_deals=duplicates,
        revenue_top20=captured, revenue_top20_oracle=oracle, revenue_top20_pct=captured / oracle,
        brier=float(v.brier.mean()),
        objection_acc=float(v.objection_ok.mean()), action_acc=float(v.action_ok.mean()),
        generic_actions=int(v.generic_action.sum()),
        fabrications=int(v.fabrications.sum()), fab_amount=int((~v.amount_ok).sum()),
        fab_gap=int((~v.gap_ok).sum()), fab_quote=int((~v.quote_ok).sum()),
        stated_pipeline=stated_total, true_pipeline=true_total,
        pipeline_error_pct=abs(stated_total - true_total) / true_total,
        reliability=rel.round(2).to_dict("index"),
    ), v


def report(co: Company, versions: list[str]) -> str:
    rows, tables = [], []
    for ver in versions:
        s, v = summarize(co, ver)
        rows.append(s)
        v.to_csv(RUNS_DIR / f"{ver}_verdicts.csv", index=False)
        tables.append((ver, s["reliability"]))
    df = pd.DataFrame(rows).set_index("version").T
    fmt = {"revenue_top20": "${:,.0f}", "revenue_top20_oracle": "${:,.0f}", "stated_pipeline": "${:,.0f}",
           "true_pipeline": "${:,.0f}"}
    lines = ["| metric | " + " | ".join(versions) + " |", "|---|" + "---|" * len(versions)]
    for k, row in df.iterrows():
        if k == "reliability":
            continue
        cells = [fmt.get(k, "{}").format(x) if not isinstance(x, float) or k in fmt else f"{x:.3f}" for x in row]
        lines.append(f"| {k} | " + " | ".join(cells) + " |")
    for ver, rel in tables:
        lines += ["", f"Reliability ({ver}): stated p bin → actual win rate"]
        for b, r in rel.items():
            lines.append(f"- {b}: n={r['n']}, stated={r['stated']}, actual={r['actual']}")
    md = "\n".join(lines)
    (Path("reports") / ("_".join(versions) + ".md")).write_text(md)
    return md

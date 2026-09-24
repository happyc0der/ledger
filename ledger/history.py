"""What changed since the last review. Pure reads over the store."""
from __future__ import annotations

import json

import pandas as pd

from . import store
from .config import DB_PATH


def _chain(run_id: str, path=DB_PATH) -> list[str]:
    """This run and all earlier runs of the same version, oldest first."""
    chain, cur = [run_id], run_id
    while (prev := store.previous_run_id(cur, path)) is not None:
        chain.append(prev)
        cur = prev
    return chain[::-1]


def summary(run_id: str, path=DB_PATH) -> dict[str, dict]:
    """Per deal: new / recurring / resolved issue keys vs the previous run, first-seen date and
    weeks open per recurring issue, stage change, close-date pushes over all runs, amount change,
    Δp, and the age of the buyer's last promise."""
    chain = _chain(run_id, path)
    runs = store.runs(path=path).set_index("run_id")
    snaps = {rid: store.snapshots(rid, path).set_index("opportunity_id") for rid in chain}
    iss = {rid: store.issues(rid, path) for rid in chain}
    first_seen: dict[str, str] = {}
    for rid in chain:
        for k in iss[rid].key:
            first_seen.setdefault(k, runs.loc[rid, "as_of"])
    cur, prev = chain[-1], (chain[-2] if len(chain) > 1 else None)
    cur_as_of = pd.Timestamp(runs.loc[cur, "as_of"])
    cur_keys = iss[cur].groupby("opportunity_id").key.apply(set).to_dict()
    prev_keys = iss[prev].groupby("opportunity_id").key.apply(set).to_dict() if prev else {}
    out = {}
    for oid, s in snaps[cur].iterrows():
        ck, pk = cur_keys.get(oid, set()), prev_keys.get(oid, set())
        rec = []
        for k in ck & pk:
            fs = pd.Timestamp(first_seen[k])
            rec.append({"key": k, "first_seen": str(fs.date()), "weeks": int(round((cur_as_of - fs).days / 7))})
        # close-date pushes: each time expected_close moved later between consecutive runs
        pushes, last = 0, None
        for rid in chain:
            if oid in snaps[rid].index:
                ec = snaps[rid].loc[oid, "expected_close"]
                if last and ec and ec > last:
                    pushes += 1
                last = ec or last
        ps = snaps[prev].loc[oid] if prev and oid in snaps[prev].index else None
        lg = json.loads(s.ledger_json) if s.ledger_json else {}
        promise_date = lg.get("last_buyer_promise_date")
        out[oid] = dict(
            new_issues=sorted(ck - pk) if prev else sorted(ck), resolved_issues=sorted(pk - ck), recurring=rec,
            stage_change=(f"{ps.stage} → {s.stage}" if ps is not None and ps.stage != s.stage else None),
            close_date_pushes=pushes,
            amount_change=(float(s.amount) - float(ps.amount) if ps is not None and ps.amount is not None and s.amount is not None else None),
            p_delta=(round(float(s.p) - float(ps.p), 2) if ps is not None and ps.p is not None and s.p is not None else None),
            promise_age_days=(int((cur_as_of - pd.Timestamp(promise_date)).days) if promise_date else None),
            previous_run=prev, first_run=(prev is None),
        )
    return out

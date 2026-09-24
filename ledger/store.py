"""Run history. Every run's deal snapshots and issues go into a per-dataset SQLite file so
the product can answer "what changed since Monday?", keep issue lifecycle state, and hold
draft CRM updates awaiting approval. Stdlib sqlite3; single writer (run.py) + readers (app)."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import DATASET, DB_PATH
from .rules import Issue

SCHEMA = """
create table if not exists runs (
  run_id text primary key, dataset text, as_of text, version text, provider text, decide_backend text,
  started text, finished text, n_deals integer, notes text);
create table if not exists deal_snapshots (
  run_id text, opportunity_id text, stage text, amount real, expected_close text, primary_contact text,
  p real, objection text, next_action text, days_since_buyer integer, record_hash text, ledger_json text,
  row_json text, primary key (run_id, opportunity_id));
create table if not exists issues (
  run_id text, key text, opportunity_id text, type text, detail text, evidence text, action text,
  severity text, source text, extra_json text, primary key (run_id, key));
create table if not exists issue_state (
  dataset text, key text, status text, who text, at text, note text, primary key (dataset, key));
create table if not exists proposals (
  id text primary key, dataset text, run_id text, opportunity_id text, issue_key text, kind text, field text,
  from_value text, to_value text, rationale text, status text, who text, at text);
create index if not exists idx_issues_run on issues(run_id);
create index if not exists idx_snap_run on deal_snapshots(run_id);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def record_run(rows: list[dict], *, as_of, version: str, provider: str = "", decide_backend: str = "",
               started: str | None = None, deals: pd.DataFrame | None = None, path: Path = DB_PATH) -> str:
    """Persist one run's rows (as written to runs/<version>.jsonl). CRM fields the rows don't carry
    (stage, expected_close, primary_contact) come from `deals` so snapshots can be diffed. Returns the run id."""
    crm = deals.set_index("opportunity_id") if deals is not None else None
    con = connect(path)
    run_id = f"{version}-{pd.Timestamp(as_of).date()}-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con.execute("insert into runs values (?,?,?,?,?,?,?,?,?,?)",
                (run_id, DATASET, str(pd.Timestamp(as_of).date()), version, provider, decide_backend, started or now, now, len(rows), ""))
    for r in rows:
        if crm is not None and r["opportunity_id"] in crm.index:
            c = crm.loc[r["opportunity_id"]]
            r = {**r, "stage": r.get("stage") or c.get("stage"), "expected_close": r.get("expected_close") or c.get("expected_close"),
                 "primary_contact": r.get("primary_contact") or c.get("primary_contact")}
        lg = r.get("ledger")
        if lg is not None:
            lg = {**lg, "quotes": r.get("ledger_quotes", {})}
        con.execute("insert or replace into deal_snapshots values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, r["opportunity_id"], r.get("stage"), _f(r.get("amount_usd")), _s(r.get("expected_close")),
                     r.get("primary_contact"), _f(r.get("win_probability")), r.get("objection"), r.get("next_action"),
                     _i(r.get("days_since_last_buyer_touch")), r.get("record_hash"), json.dumps(lg, default=str) if lg else None,
                     json.dumps({k: v for k, v in r.items() if k not in ("ledger", "ledger_quotes", "issues")}, default=str)))
        for i in r.get("issues", []):
            issue = Issue(**{k: v for k, v in i.items() if k in Issue.__dataclass_fields__})
            con.execute("insert or replace into issues values (?,?,?,?,?,?,?,?,?,?)",
                        (run_id, issue.key, issue.opportunity_id, issue.type, issue.detail, issue.evidence, issue.action,
                         issue.severity, issue.source, json.dumps(issue.extra, default=str)))
    con.commit()
    con.close()
    return run_id


def runs(version: str | None = None, path: Path = DB_PATH) -> pd.DataFrame:
    con = connect(path)
    q = "select * from runs where dataset=?" + (" and version=?" if version else "") + " order by as_of, finished"
    df = pd.read_sql_query(q, con, params=(DATASET, version) if version else (DATASET,))
    con.close()
    return df


def latest_run_id(version: str, path: Path = DB_PATH) -> str | None:
    df = runs(version, path)
    return None if df.empty else df.run_id.iloc[-1]


def previous_run_id(run_id: str, path: Path = DB_PATH) -> str | None:
    """The most recent run of the same version with an earlier as_of (or earlier finish on the same day)."""
    df = runs(path=path)
    cur = df[df.run_id == run_id]
    if cur.empty:
        return None
    v, as_of, fin = cur.version.iloc[0], cur.as_of.iloc[0], cur.finished.iloc[0]
    prev = df[(df.version == v) & ((df.as_of < as_of) | ((df.as_of == as_of) & (df.finished < fin)))]
    return None if prev.empty else prev.run_id.iloc[-1]


def snapshots(run_id: str, path: Path = DB_PATH) -> pd.DataFrame:
    con = connect(path)
    df = pd.read_sql_query("select * from deal_snapshots where run_id=?", con, params=(run_id,))
    con.close()
    return df


def issues(run_id: str, path: Path = DB_PATH) -> pd.DataFrame:
    con = connect(path)
    df = pd.read_sql_query("select * from issues where run_id=?", con, params=(run_id,))
    con.close()
    return df


def issue_states(path: Path = DB_PATH) -> dict[str, dict]:
    con = connect(path)
    out = {r["key"]: dict(r) for r in con.execute("select * from issue_state where dataset=?", (DATASET,))}
    con.close()
    return out


def set_issue_state(key: str, status: str, who: str = "", note: str = "", path: Path = DB_PATH) -> None:
    assert status in ("new", "acknowledged", "muted", "resolved")
    con = connect(path)
    con.execute("insert or replace into issue_state values (?,?,?,?,?,?)",
                (DATASET, key, status, who, datetime.now(timezone.utc).isoformat(timespec="seconds"), note))
    con.commit()
    con.close()


def rows_for(run_id: str, path: Path = DB_PATH) -> list[dict]:
    """Reconstruct run rows (as in runs/<version>.jsonl) from the store."""
    snaps, iss = snapshots(run_id, path), issues(run_id, path)
    by = {}
    for s in snaps.itertuples():
        row = json.loads(s.row_json)
        lg = json.loads(s.ledger_json) if s.ledger_json else None
        if lg is not None:
            row["ledger_quotes"] = lg.pop("quotes", {})
            row["ledger"] = lg
        row["issues"] = []
        by[s.opportunity_id] = row
    for i in iss.itertuples():
        by[i.opportunity_id]["issues"].append(dict(opportunity_id=i.opportunity_id, type=i.type, detail=i.detail, evidence=i.evidence,
                                                   action=i.action, severity=i.severity, source=i.source, extra=json.loads(i.extra_json or "{}"), key=i.key))
    return list(by.values())


def _f(x):
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None


def _i(x):
    try:
        return None if x is None or x == "" else int(x)
    except (TypeError, ValueError):
        return None


def _s(x):
    return None if x is None or x == "" else str(x)[:10]

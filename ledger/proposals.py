"""Draft CRM updates from findings. Never applied silently: a manager approves each one in the
UI, and approved drafts are exported as an import-shaped CSV for the source CRM."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import pandas as pd

from . import store
from .config import DATASET, DB_PATH
from .ingest import PRESETS


@dataclass
class Proposal:
    id: str
    opportunity_id: str
    issue_key: str
    kind: str            # update_field | close_lost | replace_primary_contact | create_task
    field: str
    from_value: str
    to_value: str
    rationale: str
    status: str = "draft"  # draft | approved | rejected | exported


def propose(issue: dict, deal: pd.Series, ledger: dict | None) -> Proposal | None:
    """One concrete, reversible edit per finding type; None when there is nothing safe to draft."""
    t, lg = issue["type"], ledger or {}
    q = issue.get("evidence", "")
    pid = uuid.uuid4().hex[:10]
    oid, key = issue["opportunity_id"], issue.get("key", "")
    if t in ("S1_past_close_date", "M4_timeline_contradiction"):
        to = lg.get("decision_date") or ""
        return Proposal(pid, oid, key, "update_field", "expected_close", str(deal.get("expected_close", ""))[:10], to or "(ask the buyer for a date)",
                        f"buyer: “{q}”" if q else issue["detail"])
    if t == "M6_zombie":
        return Proposal(pid, oid, key, "close_lost", "stage", str(deal.get("stage", "")), "Closed Lost",
                        f"buyer chose {lg.get('competitor_name') or 'a competitor'}: “{q}”")
    if t in ("M2_contact_contradiction", "M7_cross_deal_contact"):
        to = lg.get("economic_buyer") or ""
        return Proposal(pid, oid, key, "replace_primary_contact", "primary_contact", str(deal.get("primary_contact", "")),
                        to or "(identify the new contact)", f"“{q}”" if q else issue["detail"])
    if t == "M5_scope_vs_amount":
        units = lg.get("units_discussed")
        return Proposal(pid, oid, key, "update_field", "amount", str(deal.get("amount", "")), f"{units} units at list" if units else "(re-quote)",
                        f"buyer scope: “{q}”")
    if t in ("S2_no_next_step", "M3_expired_promise", "M9_missing_economic_buyer", "S3_dormant", "M8_happy_ears", "M1_stage_vs_buyer"):
        return Proposal(pid, oid, key, "create_task", "next_step", str(deal.get("next_step", "")), issue.get("action") or issue["detail"],
                        f"“{q}”" if q else issue["detail"])
    return None


def draft_for_run(co, rows: list[dict], path=DB_PATH) -> int:
    """Create drafts for every finding in a run that has none yet. Returns the number added."""
    con = store.connect(path)
    have = {r["issue_key"] for r in con.execute("select issue_key from proposals where dataset=? and status!='rejected'", (DATASET,))}
    deals = co.deals.set_index("opportunity_id")
    n = 0
    for r in rows:
        for i in r.get("issues", []):
            if not i.get("key") or i["key"] in have or i["opportunity_id"] not in deals.index:
                continue
            p = propose(i, deals.loc[i["opportunity_id"]], {**(r.get("ledger") or {}), "quotes": r.get("ledger_quotes", {})})
            if p:
                con.execute("insert into proposals values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (p.id, DATASET, "", p.opportunity_id, p.issue_key, p.kind, p.field, p.from_value, p.to_value, p.rationale, p.status, "", ""))
                have.add(i["key"]); n += 1
    con.commit(); con.close()
    return n


def list_proposals(opportunity_id: str | None = None, status: str | None = None, path=DB_PATH) -> list[dict]:
    con = store.connect(path)
    q, args = "select * from proposals where dataset=?", [DATASET]
    if opportunity_id:
        q += " and opportunity_id=?"; args.append(opportunity_id)
    if status:
        q += " and status=?"; args.append(status)
    out = [dict(r) for r in con.execute(q + " order by at desc, id", args)]
    con.close()
    return out


def set_status(pid: str, status: str, who: str = "", path=DB_PATH) -> None:
    assert status in ("draft", "approved", "rejected", "exported")
    con = store.connect(path)
    con.execute("update proposals set status=?, who=?, at=? where id=? and dataset=?",
                (status, who, datetime.now(timezone.utc).isoformat(timespec="seconds"), pid, DATASET))
    con.commit(); con.close()


def export_approved(preset: str, out_path, path=DB_PATH) -> pd.DataFrame:
    """Approved drafts as an import file in the source CRM's own column names (reverse of the
    ingest preset). Tasks go in a separate sheet-like block; nothing is written to any API."""
    cols = PRESETS[preset]["deals"]
    name = lambda f: (cols.get(f) or [f])[0]  # noqa: E731
    rows = []
    for p in list_proposals(status="approved", path=path):
        rows.append({name("opportunity_id"): p["opportunity_id"], "Field": name(p["field"]) if p["kind"] != "create_task" else "Task",
                     "Current": p["from_value"], "New": p["to_value"], "Why": p["rationale"], "Ledger proposal": p["id"]})
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    con = store.connect(path)
    con.execute("update proposals set status='exported' where dataset=? and status='approved'", (DATASET,))
    con.commit(); con.close()
    return df

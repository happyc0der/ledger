"""The baseline: what a CRM's own alert rules can see. Fields and dates only — no reading.

Each rule returns findings shaped like the agent's so the same scorer compares them.
Thresholds follow common RevOps hygiene practice (dormant 30d; stalled = 2× median cycle).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .config import SNAPSHOT
from .data import Company

LATE = {"Proposal", "Negotiation"}
MEDIAN_CYCLE_DAYS = 57


@dataclass
class Issue:
    opportunity_id: str
    type: str
    detail: str
    evidence: str = ""          # a verbatim quote for semantic issues; field values for rules
    severity: str = "medium"
    action: str = ""
    source: str = "rules"
    extra: dict = field(default_factory=dict)


def run_rules(co: Company, deals: pd.DataFrame | None = None) -> list[Issue]:
    deals = co.deals if deals is None else deals
    out: list[Issue] = []
    by_key = deals.groupby(["account", "product"]).opportunity_id.apply(list)
    for r in deals.itertuples():
        oid = r.opportunity_id
        acts = co.activities_for(oid)
        if pd.notna(r.expected_close) and r.expected_close < SNAPSHOT:
            out.append(Issue(oid, "S1_past_close_date", f"expected_close {r.expected_close.date()} is before {SNAPSHOT.date()}",
                             f"expected_close={r.expected_close.date()}", action="Update the close date or close the deal."))
        if r.stage in LATE | {"Discovery"} and (pd.isna(r.next_step) or str(r.next_step).strip() == ""):
            out.append(Issue(oid, "S2_no_next_step", "no next step recorded past Qualification", f"stage={r.stage}, next_step=''",
                             action="Record a dated next step."))
        if len(acts) and (SNAPSHOT - acts.date.max()).days > 30:
            out.append(Issue(oid, "S3_dormant", f"no activity for {(SNAPSHOT - acts.date.max()).days} days", f"last activity {acts.date.max().date()}",
                             action="Re-engage or close."))
        if r.stage in LATE and (pd.isna(r.amount) or str(r.amount).strip() == ""):
            out.append(Issue(oid, "S4_amount_blank_late", "amount blank past Qualification", f"stage={r.stage}, amount=''", action="Enter the amount."))
        if r.stage in {"Prospecting", "Qualification"} and (SNAPSHOT - r.created_date).days > 2 * MEDIAN_CYCLE_DAYS:
            out.append(Issue(oid, "S5_stalled_early_stage", f"{(SNAPSHOT - r.created_date).days} days in {r.stage} (median cycle {MEDIAN_CYCLE_DAYS}d)",
                             f"created={r.created_date.date()}, stage={r.stage}", action="Qualify out or advance."))
        sibs = [x for x in by_key.get((r.account, getattr(r, "product")), []) if x != oid]
        if sibs:
            older = deals[deals.opportunity_id.isin(sibs)].created_date.min()
            if 0 < (r.created_date - older).days <= 10 and len(acts) <= 1 and r.stage in {"Prospecting", "Qualification"}:
                out.append(Issue(oid, "S6_duplicate_deal", f"same account+product as {sibs[0]}, created within days", f"siblings={sibs}",
                                 action="Merge or close the duplicate."))
        if len(acts) and acts.date.min() < r.created_date:
            out.append(Issue(oid, "S7_activity_before_creation", f"activity on {acts.date.min().date()} predates creation {r.created_date.date()}",
                             f"first activity {acts.date.min().date()}", severity="low", action="Fix the created date or the activity date."))
        if len(acts) and pd.notna(r.last_activity_date) and (acts.date.max() - r.last_activity_date).days > 3:
            out.append(Issue(oid, "S8_last_activity_field_wrong", f"last_activity_date {r.last_activity_date.date()} but newest activity {acts.date.max().date()}",
                             f"field={r.last_activity_date.date()}, newest={acts.date.max().date()}", severity="low", action="Resync the field."))
    return out

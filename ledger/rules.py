"""The baseline: what a CRM's own alert rules can see. Fields and dates only — no reading.

Each rule returns findings shaped like the agent's so the same scorer compares them.
Thresholds follow common RevOps hygiene practice (dormant 30d; stalled = 2× median cycle).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import pandas as pd

from .config import SETTINGS, SNAPSHOT
from .data import Company

LATE = set(SETTINGS.late_stages)
MEDIAN_CYCLE_DAYS = SETTINGS.median_cycle_days
DORMANT_DAYS = SETTINGS.dormant_days
STALLED = SETTINGS.stalled_multiplier * MEDIAN_CYCLE_DAYS


@dataclass
class Check:
    """One check's outcome for one deal — pass / fail / skipped — with a one-line reason."""
    opportunity_id: str
    type: str
    status: str
    reason: str = ""


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

    KEY_VERSION = 1

    @property
    def key(self) -> str:
        """Stable identity across runs: same deal, same type, same evidence anchor. A pushed
        date or a new promise changes the anchor and therefore the key — that is a new event."""
        anchor = re.sub(r"[^a-z0-9]", "", str(self.evidence).lower())[:80]
        return hashlib.sha1(f"{self.opportunity_id}|{self.type}|{anchor}".encode()).hexdigest()[:12]


def run_rules(co: Company, deals: pd.DataFrame | None = None, as_of: pd.Timestamp = SNAPSHOT) -> list[Issue]:
    """Field-only checks as of a given review date (defaults to the configured snapshot)."""
    deals = co.deals if deals is None else deals
    out: list[Issue] = []
    off = set(SETTINGS.disabled_checks)
    by_key = deals.groupby(["account", "product"]).opportunity_id.apply(list)
    for r in deals.itertuples():
        oid = r.opportunity_id
        acts = co.activities_for(oid)
        if pd.notna(r.expected_close) and r.expected_close < as_of:
            out.append(Issue(oid, "S1_past_close_date", f"expected_close {r.expected_close.date()} is before {as_of.date()}",
                             f"expected_close={r.expected_close.date()}", action="Update the close date or close the deal."))
        if r.stage in LATE | {"Discovery"} and (pd.isna(r.next_step) or str(r.next_step).strip() == ""):
            out.append(Issue(oid, "S2_no_next_step", "no next step recorded past Qualification", f"stage={r.stage}, next_step=''",
                             action="Record a dated next step."))
        if len(acts) and (as_of - acts.date.max()).days > DORMANT_DAYS:
            out.append(Issue(oid, "S3_dormant", f"no activity for {(as_of - acts.date.max()).days} days", f"last activity {acts.date.max().date()}",
                             action="Re-engage or close."))
        if r.stage in LATE and (pd.isna(r.amount) or str(r.amount).strip() == ""):
            out.append(Issue(oid, "S4_amount_blank_late", "amount blank past Qualification", f"stage={r.stage}, amount=''", action="Enter the amount."))
        if r.stage in {"Prospecting", "Qualification"} and (as_of - r.created_date).days > STALLED:
            out.append(Issue(oid, "S5_stalled_early_stage", f"{(as_of - r.created_date).days} days in {r.stage} (median cycle {MEDIAN_CYCLE_DAYS}d)",
                             f"created={r.created_date.date()}, stage={r.stage}", action="Qualify out or advance."))
        sibs = [x for x in by_key.get((r.account, getattr(r, "product")), []) if x != oid]
        if sibs:
            earlier = deals[deals.opportunity_id.isin(sibs) & (deals.created_date < r.created_date)].created_date
            older = earlier.max() if len(earlier) else None  # nearest earlier sibling
            if older is not None and (r.created_date - older).days <= 10 and len(acts) <= 1 and r.stage in {"Prospecting", "Qualification"}:
                out.append(Issue(oid, "S6_duplicate_deal", f"same account+product as {sibs[0]}, created within days", f"siblings={sibs}",
                                 action="Merge or close the duplicate."))
        if len(acts) and acts.date.min() < r.created_date:
            out.append(Issue(oid, "S7_activity_before_creation", f"activity on {acts.date.min().date()} predates creation {r.created_date.date()}",
                             f"first activity {acts.date.min().date()}", severity="low", action="Fix the created date or the activity date."))
        if len(acts) and pd.notna(r.last_activity_date) and (acts.date.max() - r.last_activity_date).days > 3:
            out.append(Issue(oid, "S8_last_activity_field_wrong", f"last_activity_date {r.last_activity_date.date()} but newest activity {acts.date.max().date()}",
                             f"field={r.last_activity_date.date()}, newest={acts.date.max().date()}", severity="low", action="Resync the field."))
    return [i for i in out if i.type not in off]


RULE_TYPES = ["S1_past_close_date", "S2_no_next_step", "S3_dormant", "S4_amount_blank_late", "S5_stalled_early_stage",
              "S6_duplicate_deal", "S7_activity_before_creation", "S8_last_activity_field_wrong"]


def checks_for(co: Company, oid: str, issues: list[Issue], as_of: pd.Timestamp = SNAPSHOT) -> list[Check]:
    """Pass/fail/skipped for every rule on one deal (fail = an issue of that type exists)."""
    d = co.deal(oid); acts = co.activities_for(oid)
    failed = {i.type for i in issues if i.opportunity_id == oid}
    off = set(SETTINGS.disabled_checks)
    why = {
        "S1_past_close_date": ("skipped", "no close date") if pd.isna(d.expected_close) else ("pass", f"close date {d.expected_close.date()} is ahead"),
        "S2_no_next_step": ("skipped", f"stage {d.stage} is early") if d.stage not in LATE | {"Discovery"} else ("pass", "next step recorded"),
        "S3_dormant": ("skipped", "no activity") if not len(acts) else ("pass", f"last activity {(as_of - acts.date.max()).days}d ago"),
        "S4_amount_blank_late": ("skipped", f"stage {d.stage} is early") if d.stage not in LATE else ("pass", "amount entered"),
        "S5_stalled_early_stage": ("skipped", f"stage {d.stage} is not early") if d.stage not in {"Prospecting", "Qualification"} else ("pass", f"{(as_of - d.created_date).days}d old, limit {int(STALLED)}"),
        "S6_duplicate_deal": ("pass", "no sibling deal created within days"),
        "S7_activity_before_creation": ("skipped", "no activity") if not len(acts) else ("pass", "activities after creation"),
        "S8_last_activity_field_wrong": ("skipped", "no activity or field") if not len(acts) or pd.isna(d.last_activity_date) else ("pass", "field matches newest activity"),
    }
    out = []
    for t in RULE_TYPES:
        if t in off:
            out.append(Check(oid, t, "skipped", "disabled in settings"))
        elif t in failed:
            out.append(Check(oid, t, "fail", next(i.detail for i in issues if i.opportunity_id == oid and i.type == t)))
        else:
            st, reason = why[t]
            out.append(Check(oid, t, st, reason))
    return out

"""The naive way to find pipeline issues: hand the model a batch of deals and ask it to list
everything wrong, with a type from our taxonomy and a quote. This is what KC-Bench says fails —
explicit conflicts get missed, and issues get invented. Kept as a measured comparison."""
from __future__ import annotations

import json

from . import llm, tracing
from .agent_v1 import _render_deals
from .config import SNAPSHOT
from .data import Company
from .score_issues import TYPES

BATCH = 25
DESC = {
    "S1_past_close_date": "expected close date is in the past", "S2_no_next_step": "no next step recorded on a deal past Qualification",
    "S3_dormant": "no activity for more than 30 days", "S4_amount_blank_late": "amount blank on a deal past Qualification",
    "S5_stalled_early_stage": "stuck in Prospecting/Qualification for more than ~4 months", "S6_duplicate_deal": "duplicate of another open deal (same account and product, created days apart)",
    "S7_activity_before_creation": "an activity dated before the deal was created", "S8_last_activity_field_wrong": "last_activity field older than the newest activity",
    "M1_stage_vs_buyer": "rep-set stage contradicts what the buyer said (e.g. Negotiation but budget frozen / chose competitor / paused)",
    "M2_contact_contradiction": "primary contact left the company, or doesn't own the decision, or CRM economic buyer differs from the person the buyer names",
    "M3_expired_promise": "buyer promised something (PO, signature, callback) more than 14 days ago and has been silent since",
    "M4_timeline_contradiction": "expected close date is before the buyer's stated decision date, or budget is frozen / onboarding paused",
    "M5_scope_vs_amount": "buyer discussed multiple units but the CRM amount is for one", "M6_zombie": "buyer already chose a competitor; deal still open",
    "M7_cross_deal_contact": "the primary contact was reported gone on ANOTHER deal at the same account", "M8_happy_ears": "rep note stays positive after the buyer paused/declined/leaned away",
    "M9_missing_economic_buyer": "late-stage deal with no economic buyer in the CRM contacts", "M10_arithmetic": "buyer's stated total doesn't equal units × list price",
}
SCHEMA = {"type": "object", "properties": {"issues": {"type": "array", "items": {"type": "object", "properties": {
    "opportunity_id": {"type": "string"}, "type": {"type": "string", "enum": TYPES}, "detail": {"type": "string"}, "evidence": {"type": "string"}},
    "required": ["opportunity_id", "type", "detail", "evidence"]}}}, "required": ["issues"]}


def run_rep(co: Company, rep: str, *, limit: int | None = None) -> list[dict]:
    deals = co.deals_for(rep)
    if limit:
        deals = deals.head(limit)
    session = f"naive-{rep.replace(' ', '_')}"
    catalogue = "\n".join(f"- {r.product}: ${r.sales_price:,.0f}" for r in co.products.itertuples())
    contacts = co.contacts[co.contacts.opportunity_id.isin(deals.opportunity_id)]
    found: dict[str, list] = {oid: [] for oid in deals.opportunity_id}
    for i in range(0, len(deals), BATCH):
        batch = deals.iloc[i:i + BATCH]
        cts = "\n".join(f"- {c.opportunity_id}: {c.name} ({c.title}, {c.role})" for c in contacts[contacts.opportunity_id.isin(batch.opportunity_id)].itertuples())
        system = (f"Today is {SNAPSHOT.date()}. You are a pipeline auditor. Read these deals and their activity records and list EVERY issue "
                  f"you can find, using these types:\n{json.dumps(DESC, indent=1)}\nCatalogue list prices:\n{catalogue}\n"
                  "For each issue give the opportunity_id, the type, a one-line detail and a verbatim evidence sentence from the record "
                  "(or the field values). Be thorough but do not invent issues.")
        user = f"Rep: {rep}\n\nContacts in CRM:\n{cts}\n\n{_render_deals(co, batch)}"
        _, parsed = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}], schema=SCHEMA,
                             version="naive", session_id=session, metadata={"rep": rep, "batch": i // BATCH, "role": "naive-issues"})
        for it in (parsed or {}).get("issues", []):
            if it.get("opportunity_id") in found and it.get("type") in TYPES:
                found[it["opportunity_id"]].append({**it, "action": "", "severity": "medium", "source": "naive"})
    rows = [dict(opportunity_id=oid, issues=iss, version="naive", rep=rep, win_probability=0.5, amount_usd=0, rank=0,
                 days_since_last_buyer_touch=0, objection="none", buyer_quote="", next_action="", rationale="", pipeline_total_usd=0, batch=0)
            for oid, iss in found.items()]
    tracing.trajectory(version="naive", session_id=session, steps=[tracing.step("final_answer", f"{sum(len(v) for v in found.values())} issues")], model="naive")
    return rows

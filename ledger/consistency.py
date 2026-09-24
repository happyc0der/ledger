"""Compare each deal's claim ledger against its CRM fields. Pure code; every issue carries
the CRM value, the buyer quote and the date. Cross-deal checks look across an account."""
from __future__ import annotations

import re
from datetime import timedelta

import pandas as pd

from .config import SNAPSHOT
from .data import Company
from .rules import LATE, Issue
from .tools import deal_amount, list_price, normalize_product

ACTIONS = {
    "M1_stage_vs_buyer": "Move the stage back to match the buyer, or disqualify.",
    "M2_contact_contradiction": "Update the contact record; multithread to the named decision-maker.",
    "M3_expired_promise": "Ask the buyer directly what changed; set a real close date.",
    "M4_timeline_contradiction": "Move expected_close to the buyer's stated decision date.",
    "M5_scope_vs_amount": "Re-quote for the scope the buyer described; update the amount.",
    "M6_zombie": "Close-lost with the competitor as reason.",
    "M7_cross_deal_contact": "Replace the primary contact; confirm the deal is still alive.",
    "M8_happy_ears": "Coach the rep: the buyer's last message outranks the rep's optimism.",
    "M9_missing_economic_buyer": "Identify and log the economic buyer before forecasting this deal.",
    "M10_arithmetic": "Correct the total in writing before it reaches a PO.",
}


def _q(ledger: dict, slot: str) -> str:
    return ledger.get("quotes", {}).get(slot, "")


def compare(co: Company, oid: str, ledger: dict, as_of: pd.Timestamp = SNAPSHOT) -> list[Issue]:
    d = co.deal(oid)
    out: list[Issue] = []
    late = d.stage in LATE
    dt = lambda s: pd.Timestamp(s) if s else None  # noqa: E731

    def add(t, detail, slot, **extra):
        grade = (ledger.get("grades") or {}).get(slot, "B")
        sev = "low" if grade == "C" else "medium"
        out.append(Issue(oid, t, detail, _q(ledger, slot), severity=sev, action=ACTIONS[t], source="ledger",
                         extra={**extra, "evidence_grade": grade}))

    # "Leaning toward MG Special" is leaning toward US: a named competitor that is one of our own
    # products is not a competitor (comparison fix, disclosed in README).
    ours = {normalize_product(p) for p in co.products["product"]}
    if ledger.get("competitor_status") in ("leaning_competitor", "chose_competitor"):
        named = normalize_product(str(ledger.get("competitor_name") or ""))
        quote = normalize_product(_q(ledger, "competitor_status"))
        names_in_quote = {p for p in ours if p and p in quote}
        if named in ours or (not named and names_in_quote):
            ledger = {**ledger, "competitor_status": "chose_us" if ledger["competitor_status"] == "chose_competitor" else "evaluating"}

    # M1 stage vs buyer / M6 zombie
    if ledger.get("competitor_status") == "chose_competitor":
        add("M6_zombie", f"buyer chose {ledger.get('competitor_name') or 'a competitor'}; stage is {d.stage}", "competitor_status")
        if late:
            add("M1_stage_vs_buyer", f"stage {d.stage} but buyer chose a competitor", "competitor_status")
    elif late and (ledger.get("budget_status") == "frozen" or ledger.get("commitment") in ("declined", "paused")
                   or ledger.get("competitor_status") == "leaning_competitor"):
        why = {"frozen": "budget frozen", "declined": "buyer declined", "paused": "buyer paused", "leaning_competitor": "buyer leaning to a competitor"}
        key = ledger.get("budget_status") if ledger.get("budget_status") == "frozen" else (ledger.get("commitment") if ledger.get("commitment") in ("declined", "paused") else "leaning_competitor")
        slot = "budget_status" if key == "frozen" else ("commitment" if key in ("declined", "paused") else "competitor_status")
        add("M1_stage_vs_buyer", f"stage {d.stage} but {why[key]}", slot)
    # M2 contact contradictions
    if ledger.get("champion_status") == "left_company":
        add("M2_contact_contradiction", f"primary contact {d.primary_contact} has left; still primary", "champion_status")
    crm_econ = co.contacts[(co.contacts.opportunity_id == oid) & (co.contacts.role == "economic_buyer")]
    named = ledger.get("economic_buyer")
    if named and len(crm_econ) and not _same_person(named, crm_econ.iloc[0]["name"]):
        add("M2_contact_contradiction", f"CRM economic buyer is {crm_econ.iloc[0]['name']}; buyer names {named}", "economic_buyer")
    if ledger.get("champion_status") == "no_authority" and late:
        add("M2_contact_contradiction", f"primary contact says they don't own the decision; stage is {d.stage}", "champion_status")
    # M3 expired promise
    pdate = dt(ledger.get("last_buyer_promise_date"))
    if ledger.get("last_buyer_promise") and pdate is not None and (as_of - pdate).days > 14 \
            and ledger.get("commitment") not in ("declined", "paused"):  # a declined/paused buyer owes nothing
        add("M3_expired_promise", f"buyer promised '{ledger['last_buyer_promise'][:60]}' {(as_of - pdate).days}d ago; nothing since", "last_buyer_promise")
    # M4 timeline
    ddate = dt(ledger.get("decision_date"))
    close_future = pd.notna(d.expected_close) and d.expected_close >= as_of  # a past close date is S1, not M4
    if ddate is not None and close_future and d.expected_close < ddate - timedelta(days=2):
        add("M4_timeline_contradiction", f"expected_close {d.expected_close.date()} is before the buyer's decision date {ddate.date()}", "decision_date")
    if close_future and d.expected_close < as_of + timedelta(days=75):
        if ledger.get("budget_status") == "frozen":
            add("M4_timeline_contradiction", f"expected_close {d.expected_close.date()} but the buyer said budget is frozen", "budget_status")
        elif ledger.get("commitment") == "paused":
            add("M4_timeline_contradiction", f"expected_close {d.expected_close.date()} but the buyer paused with no date", "commitment")
    # M5 scope / M10 arithmetic
    units, total = ledger.get("units_discussed"), ledger.get("total_stated_usd")
    try:
        units = int(units) if units not in (None, "") else None
        total = float(total) if total not in (None, "") else None
    except (TypeError, ValueError):
        units = total = None
    lp = list_price(co.products, d["product"])
    if lp is None:  # no catalogue: fall back to the CRM amount as the unit price when scope is 1
        lp = deal_amount(co.products, d) if not units or units == 1 else None
    if lp is None:
        pass  # cannot check scope/arithmetic without a unit price
    elif units and total and abs(total - units * lp) / max(units * lp, 1) > 0.05:
        add("M10_arithmetic", f"buyer says {units} × ${lp:,.0f} = ${total:,.0f}; that is ${units * lp:,.0f}", "total_stated_usd")
    elif units and units > 1 and abs(deal_amount(co.products, d) - units * lp) > 1:
        add("M5_scope_vs_amount", f"buyer scope {units} units (${units * lp:,.0f}); CRM amount ${deal_amount(co.products, d):,.0f}", "units_discussed")
    # M8 happy ears
    if ledger.get("rep_sentiment_after_last_buyer_message") == "positive" and (
            ledger.get("commitment") in ("declined", "paused") or ledger.get("budget_status") == "frozen"
            or ledger.get("competitor_status") in ("leaning_competitor", "chose_competitor")):
        add("M8_happy_ears", "rep stayed positive after the buyer paused, declined or leaned away", "commitment" if ledger.get("commitment") in ("declined", "paused") else ("budget_status" if ledger.get("budget_status") == "frozen" else "competitor_status"))
    # M9 missing economic buyer
    if late and not len(crm_econ):
        out.append(Issue(oid, "M9_missing_economic_buyer", "late stage, no economic buyer in CRM" + (f"; buyer names {named}" if named else ""),
                         _q(ledger, "economic_buyer") if named else f"stage={d.stage}, contacts={list(co.contacts[co.contacts.opportunity_id == oid].role)}",
                         action=ACTIONS["M9_missing_economic_buyer"], source="ledger"))
    return out


def _last(name: str) -> str:
    return str(name).strip().split()[-1].lower() if name else ""


def _same_person(a: str, b: str) -> bool:
    """Paraphrased notes shorten names ('Samuel' for 'Samuel Osei'): match on any shared name token."""
    ta = {t.lower() for t in str(a or "").replace(",", " ").split() if len(t) > 1}
    tb = {t.lower() for t in str(b or "").replace(",", " ").split() if len(t) > 1}
    return bool(ta & tb)


def cross_deal(co: Company, ledgers: dict[str, dict]) -> list[Issue]:
    """M7: a contact reported gone on one deal is still primary on another deal at the same account."""
    out = []
    gone = {}
    for oid, lg in ledgers.items():
        if lg.get("champion_status") == "left_company":
            d = co.deal(oid)
            gone.setdefault((d.account, str(d.primary_contact).strip().lower()), (oid, _q(lg, "champion_status")))
    for r in co.deals.itertuples():
        key = (r.account, str(r.primary_contact).strip().lower())
        if key in gone and gone[key][0] != r.opportunity_id and ledgers.get(r.opportunity_id, {}).get("champion_status") != "left_company":
            src, quote = gone[key]
            out.append(Issue(r.opportunity_id, "M7_cross_deal_contact", f"primary contact {r.primary_contact} left {r.account} per auto-reply on deal {src}",
                             quote, action=ACTIONS["M7_cross_deal_contact"], source="ledger", extra={"source_deal": src}))
    return out

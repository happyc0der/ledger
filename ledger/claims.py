"""The claim ledger: buyer-stated facts extracted from the record, each with a quote.

The model READS; it never compares. Every slot is null unless the buyer (or a system
message such as an auto-reply) actually said it, and every non-null slot carries a
verbatim quote and the date it was said. ledger/consistency.py does the comparing.
"""
from __future__ import annotations

import json
import re

import pandas as pd

from . import llm
from .config import SNAPSHOT
from .data import Company

SLOTS = {
    "budget_status": ["unknown", "approved", "constrained", "frozen", "no_budget_owner"],
    "decision_timeline": "free text as the buyer stated it, or null",
    "decision_date": "ISO date if the buyer gave or implied one (e.g. 'decision in three weeks' from the message date), else null",
    "economic_buyer": "person the buyer names as approver/budget owner, else null",
    "champion_status": ["unknown", "active", "left_company", "no_authority"],
    "_hints": {
        "champion_status": "left_company if ANY message (especially a system auto-reply, even lowercase/unpunctuated) says the "
                           "contact left / is no longer with the company; no_authority if the buyer says they don't own the budget or decision.",
        "budget_status": "frozen if capex/budget is frozen or 'no budget line'; constrained if the price is a stretch; approved if a named person approved it.",
        "competitor_status": "chose_competitor if the buyer says they went with / decided on / chose another vendor; leaning_competitor if leaning; chose_us if they picked us.",
        "commitment": "po_in_flight if a PO/order form/paperwork is being routed; verbal_yes if 'going ahead' without paperwork; paused/declined per the buyer's words.",
        "last_buyer_promise": "the buyer's most recent statement of what happens next ('PO next week', 'I'll get back to you'), verbatim.",
        "units_discussed / total_stated_usd": "only if the buyer states a unit count or a dollar total.",
        "economic_buyer": "the person the buyer names as approving/owning budget (not the rep, not the primary contact unless they say so).",
    },
    "competitor_status": ["none_mentioned", "evaluating", "leaning_competitor", "chose_competitor", "chose_us"],
    "competitor_name": "name or null",
    "product_discussed": "product name as the buyer wrote it, or null",
    "units_discussed": "integer or null",
    "total_stated_usd": "number the buyer stated as a total, or null",
    "commitment": ["none", "verbal_yes", "po_in_flight", "signed", "declined", "paused"],
    "last_buyer_promise": "what the buyer said would happen next and by when, or null",
    "last_buyer_promise_date": "ISO date of the message containing that promise, or null",
    "rep_sentiment_after_last_buyer_message": ["n/a", "positive", "neutral", "negative"],
}

SCHEMA = {
    "type": "object",
    "properties": {
        **{k: ({"type": ["string", "null"], "enum": v + [None]} if isinstance(v, list) else {"type": ["string", "number", "null"]}) for k, v in SLOTS.items() if k != "_hints"},
        "quotes": {"type": "object", "additionalProperties": {"type": "string"}},
    },
    "required": [k for k in SLOTS if k != "_hints"] + ["quotes"],
}


def _record(co: Company, oid: str) -> tuple[dict, list[dict]]:
    """The deal and its activities as the model sees them: PII tokenised, roles resolved."""
    from .redact import Redactor
    d = co.deal(oid)
    acts = co.activities_for(oid)
    red = Redactor()
    rows = []
    for i, a in enumerate(acts.itertuples()):
        role = getattr(a, "speaker", None) or ("rep" if a.author == d.sales_agent else ("system" if a.author == "system" else "buyer"))
        rows.append({"n": i + 1, "date": str(a.date.date()), "type": a.type, "author": a.author, "role": role,
                     "basis": getattr(a, "speaker_basis", "legacy"), "text": red.redact(a.text)})
    d = d.copy(); d["_redactor"] = red
    return d, rows


def extract(co: Company, oid: str, *, version: str, session: str) -> dict:
    d, rows = _record(co, oid)
    system = (
        "You are filling a claim ledger for one sales opportunity from its activity "
        "record. Only the BUYER's own words (author role 'buyer', including buyer sentences quoted inside rep notes "
        "as Buyer: \"...\") and SYSTEM messages (auto-replies) count as evidence. The rep's opinions do not. "
        "For every non-null slot, put a VERBATIM sentence from the record in quotes[slot]. If the buyer never "
        "said it, the slot is null — never infer from the rep or from the CRM. Slots:\n"
        + json.dumps(SLOTS, indent=1)
        + "\nrep_sentiment_after_last_buyer_message: the tone of any REP note dated after the buyer's last message."
    )
    user = json.dumps({"deal": {"opportunity_id": oid, "product": d["product"], "rep": d.sales_agent}, "activities": rows}, default=str)
    _, parsed = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}], schema=SCHEMA,
                         version=version, session_id=session, metadata={"deal_id": oid, "role": "claim-ledger"})
    ledger = {k: (parsed or {}).get(k) for k in SLOTS if k != "_hints"}
    ledger["quotes"] = (parsed or {}).get("quotes") or {}
    ledger = verify(ledger, rows)  # verified against the redacted record the model saw
    red = d.get("_redactor")
    if red is not None and red.map:  # then shown with the real values
        ledger["quotes"] = {k: red.inflate(v) for k, v in ledger["quotes"].items()}
        for k in ("economic_buyer", "last_buyer_promise", "decision_timeline"):
            if isinstance(ledger.get(k), str):
                ledger[k] = red.inflate(ledger[k])
    return ledger


def extract_uncached(co: Company, oid: str, *, version: str, session: str) -> dict:
    """Same extraction, cache bypassed — for agreement measurement."""
    import ledger.llm as _llm
    orig = _llm.chat
    def nocache(*a, **k):
        k["use_cache"] = False
        return orig(*a, **k)
    _llm.chat = nocache
    try:
        return extract(co, oid, version=version, session=session)
    finally:
        _llm.chat = orig


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower().replace("’", "'")).strip()


NULLISH = (None, "", "unknown", "none_mentioned", "none", "n/a")
# slots whose evidence is their parent's quote (dates and numbers are not sentences)
PARENT = {"decision_date": "decision_timeline", "last_buyer_promise_date": "last_buyer_promise",
          "units_discussed": "product_discussed", "total_stated_usd": "product_discussed", "competitor_name": "competitor_status"}
NO_QUOTE_NEEDED = {"rep_sentiment_after_last_buyer_message"}


def _find_row(rows: list[dict], quote: str) -> dict | None:
    q = _norm(quote)
    for r in rows:
        if q and q in _norm(r["text"]):
            return r
    return None


GRADE = {"direction": "A", "from-domain": "A", "auto-reply": "A", "author-contact": "B", "legacy": "B"}


def _admissible(row: dict, quote: str) -> str | None:
    """Evidence grade for a quote found in this row, or None if the row can't carry buyer evidence.
    A: buyer/system row by direction or address; B: buyer row by author name; C: quoted inside a rep note."""
    if row["role"] in ("buyer", "system"):
        return GRADE.get(row.get("basis", "legacy"), "B")
    from .attribution import segments
    q = _norm(quote)
    for kind, span in segments(row["text"]):
        if q and q in _norm(span):
            return "C"
    return None


def verify(ledger: dict, rows: list[dict]) -> dict:
    """A claim without a verbatim buyer/system quote is reset to null; dates are taken from the
    activity that contains the quote, not from the model. Returns ledger + 'dropped' list."""
    dropped = []
    quotes = ledger.get("quotes") or {}
    kept, grades = {}, {}
    for slot in SLOTS:
        if slot == "_hints" or slot in NO_QUOTE_NEEDED or ledger.get(slot) in NULLISH:
            continue
        q = quotes.get(slot) or quotes.get(PARENT.get(slot, ""), "")
        row = _find_row(rows, q) if q else None
        grade = _admissible(row, q) if row is not None else None
        if grade is None:
            dropped.append(slot)
            ledger[slot] = None
        else:
            kept[slot] = q
            grades[slot] = grade
    ledger["quotes"] = kept
    ledger["grades"] = grades
    # dates come from the record, never from the model
    if ledger.get("last_buyer_promise"):
        row = _find_row(rows, kept.get("last_buyer_promise", ""))
        ledger["last_buyer_promise_date"] = row["date"] if row else None
    if ledger.get("decision_date"):
        row = _find_row(rows, kept.get("decision_timeline", kept.get("decision_date", "")))
        try:
            dd = pd.Timestamp(ledger["decision_date"])
            base = pd.Timestamp(row["date"]) if row else None
            if base is None or not (base <= dd <= base + pd.Timedelta(days=180)):
                ledger["decision_date"] = None
                dropped.append("decision_date")
        except (TypeError, ValueError):
            ledger["decision_date"] = None
    ledger["dropped"] = dropped
    return ledger

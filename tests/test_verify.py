from ledger.claims import verify

ROWS = [
    {"n": 1, "date": "2026-10-01", "type": "call", "author": "Rep One", "role": "rep", "basis": "author-rep",
     "text": 'Demo with Priya. Buyer: "Honestly the number is higher than what we budgeted."'},
    {"n": 2, "date": "2026-10-05", "type": "email", "author": "Priya Okafor", "role": "buyer", "basis": "author-contact",
     "text": "PO should go out next week."},
]


def test_quote_in_buyer_row_kept_grade_b():
    lg = {"commitment": "po_in_flight", "last_buyer_promise": "PO should go out next week.",
          "quotes": {"commitment": "PO should go out next week.", "last_buyer_promise": "PO should go out next week."}}
    v = verify(lg, ROWS)
    assert v["commitment"] == "po_in_flight" and v["grades"]["commitment"] == "B"
    assert v["last_buyer_promise_date"] == "2026-10-05"  # date comes from the record, not the model


def test_quote_inside_rep_note_is_grade_c():
    lg = {"budget_status": "constrained", "quotes": {"budget_status": "the number is higher than what we budgeted"}}
    v = verify(lg, ROWS)
    assert v["budget_status"] == "constrained" and v["grades"]["budget_status"] == "C"


def test_missing_or_invented_quote_is_dropped():
    lg = {"competitor_status": "chose_competitor", "quotes": {"competitor_status": "we went with Kestrel"}}
    v = verify(lg, ROWS)
    assert v["competitor_status"] is None and "competitor_status" in v["dropped"]


def test_decision_date_must_be_near_its_quote():
    lg = {"decision_timeline": "next week", "decision_date": "2027-06-01", "quotes": {"decision_timeline": "PO should go out next week."}}
    v = verify(lg, ROWS)
    assert v["decision_date"] is None

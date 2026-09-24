from conftest import AS_OF, make_company
from ledger.rules import Issue, run_rules


def types(co):
    return {i.type for i in run_rules(co, as_of=AS_OF)}


def test_past_close_date_and_no_next_step(one_deal):
    co = make_company([{**one_deal, "expected_close": "2026-10-01", "next_step": ""}], [("a", "D1", "2026-10-10", "call", "Rep One", "x")])
    assert {"S1_past_close_date", "S2_no_next_step"} <= types(co)


def test_dormant_and_blank_amount(one_deal):
    co = make_company([{**one_deal, "amount": None}], [("a", "D1", "2026-09-01", "call", "Rep One", "x")])
    assert {"S3_dormant", "S4_amount_blank_late"} <= types(co)


def test_duplicate_needs_nearby_creation_and_no_history(one_deal):
    dup = {**one_deal, "opportunity_id": "D1DP", "created_date": "2026-08-03", "stage": "Prospecting"}
    co = make_company([one_deal, dup], [("a", "D1", "2026-10-10", "call", "Rep One", "x"), ("b", "D1DP", "2026-08-03", "call", "Rep One", "intro")])
    assert [i.opportunity_id for i in run_rules(co, as_of=AS_OF) if i.type == "S6_duplicate_deal"] == ["D1DP"]


def test_issue_key_is_stable_and_anchored():
    a = Issue("D1", "M3_expired_promise", "d", "PO next week"); b = Issue("D1", "M3_expired_promise", "other", "po next week!")
    c = Issue("D1", "M3_expired_promise", "d", "PO in January")
    assert a.key == b.key and a.key != c.key

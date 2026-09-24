import pandas as pd

from conftest import AS_OF, make_company
from ledger.consistency import compare, cross_deal


def co_with(one_deal, acts, contacts=None, **over):
    d = {**one_deal, **over}
    return make_company([d], acts, contacts)


def types(issues):
    return {i.type for i in issues}


def test_stage_vs_frozen_budget(one_deal):
    co = co_with(one_deal, [("D1-1", "D1", "2026-10-01", "email", "Priya Okafor", "capex is frozen until next fiscal year")])
    lg = {"budget_status": "frozen", "quotes": {"budget_status": "capex is frozen until next fiscal year"}, "grades": {"budget_status": "B"}}
    t = types(compare(co, "D1", lg, as_of=AS_OF))
    assert "M1_stage_vs_buyer" in t and "M4_timeline_contradiction" in t


def test_zombie_when_buyer_chose_competitor(one_deal):
    co = co_with(one_deal, [("D1-1", "D1", "2026-10-01", "email", "Priya Okafor", "we went with Kestrel Compute")])
    lg = {"competitor_status": "chose_competitor", "competitor_name": "Kestrel Compute",
          "quotes": {"competitor_status": "we went with Kestrel Compute"}, "grades": {}}
    assert "M6_zombie" in types(compare(co, "D1", lg, as_of=AS_OF))


def test_leaning_toward_our_own_product_is_not_a_competitor(one_deal):
    co = co_with(one_deal, [("D1-1", "D1", "2026-10-01", "email", "Priya Okafor", "they are leaning toward GTX Basic")])
    lg = {"competitor_status": "leaning_competitor", "competitor_name": None,
          "quotes": {"competitor_status": "they are leaning toward GTX Basic"}, "grades": {}}
    assert "M1_stage_vs_buyer" not in types(compare(co, "D1", lg, as_of=AS_OF))


def test_expired_promise_and_near_miss(one_deal):
    co = co_with(one_deal, [("D1-1", "D1", "2026-09-20", "email", "Priya Okafor", "PO next week")])
    lg = {"last_buyer_promise": "PO next week", "last_buyer_promise_date": "2026-09-20", "commitment": "verbal_yes",
          "quotes": {"last_buyer_promise": "PO next week"}, "grades": {}}
    assert "M3_expired_promise" in types(compare(co, "D1", lg, as_of=AS_OF))
    lg["last_buyer_promise_date"] = "2026-10-12"  # 7 days ago: not expired
    assert "M3_expired_promise" not in types(compare(co, "D1", lg, as_of=AS_OF))


def test_arithmetic_and_scope(one_deal):
    co = co_with(one_deal, [("D1-1", "D1", "2026-10-01", "email", "Priya Okafor", "3 units at list, so $2,000 total")])
    lg = {"units_discussed": 3, "total_stated_usd": 2000, "product_discussed": "GTX Basic",
          "quotes": {"product_discussed": "3 units at list, so $2,000 total"}, "grades": {}}
    assert "M10_arithmetic" in types(compare(co, "D1", lg, as_of=AS_OF))
    lg["total_stated_usd"] = 1650  # correct total, but CRM amount is one unit
    assert "M5_scope_vs_amount" in types(compare(co, "D1", lg, as_of=AS_OF))


def test_missing_economic_buyer_only_late_stage(one_deal):
    co = co_with(one_deal, [("D1-1", "D1", "2026-10-01", "call", "Rep One", "intro")])
    assert "M9_missing_economic_buyer" in types(compare(co, "D1", {"quotes": {}, "grades": {}}, as_of=AS_OF))
    co2 = co_with(one_deal, [("D1-1", "D1", "2026-10-01", "call", "Rep One", "intro")], stage="Discovery")
    assert "M9_missing_economic_buyer" not in types(compare(co2, "D1", {"quotes": {}, "grades": {}}, as_of=AS_OF))


def test_cross_deal_contact_left(one_deal):
    d2 = {**one_deal, "opportunity_id": "D2", "product": "GTX Basic"}
    co = make_company([one_deal, d2], [("D1-1", "D1", "2026-10-02", "email", "system", "Auto-reply: Priya Okafor is no longer with Acme.")])
    ledgers = {"D1": {"champion_status": "left_company", "quotes": {"champion_status": "Priya Okafor is no longer with Acme."}}, "D2": {}}
    found = cross_deal(co, ledgers)
    assert [i.opportunity_id for i in found] == ["D2"] and found[0].type == "M7_cross_deal_contact"


def test_c_grade_evidence_lowers_severity(one_deal):
    co = co_with(one_deal, [("D1-1", "D1", "2026-10-01", "email", "Priya Okafor", "we went with Kestrel")])
    lg = {"competitor_status": "chose_competitor", "competitor_name": "Kestrel", "quotes": {"competitor_status": "we went with Kestrel"},
          "grades": {"competitor_status": "C"}}
    assert all(i.severity == "low" for i in compare(co, "D1", lg, as_of=AS_OF) if i.type == "M6_zombie")

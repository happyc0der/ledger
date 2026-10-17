from conftest import make_company

from ledger.agent_v1 import verify_rows


def _co():
    deals = [dict(opportunity_id="D1", account="Acme", product="GTX Basic", sales_agent="Rep One", stage="Negotiation", amount=550.0,
                  created_date="2026-08-01", expected_close="2026-11-15", primary_contact="Priya Okafor",
                  last_activity_date="2026-10-10", next_step="Send proposal")]
    acts = [("A1", "D1", "2026-10-10", "email", "Priya Okafor", "Budget is frozen until January, sorry.")]
    return make_company(deals, acts, contacts=[("D1", "Priya Okafor", "CFO", "economic_buyer")])


def test_supported_answer_has_no_error_steps():
    co = _co()
    steps = verify_rows(co, [dict(opportunity_id="D1", amount_usd=550, days_since_last_buyer_touch=9, buyer_quote="Budget is frozen until January")])
    assert [s["label"] for s in steps] == ["check:summary"] and steps[-1]["status"] == "success"


def test_fabricated_quote_amount_and_gap_are_error_steps():
    co = _co()
    steps = verify_rows(co, [dict(opportunity_id="D1", amount_usd=5000, days_since_last_buyer_touch=2, buyer_quote="We signed yesterday")])
    labels = [s["label"] for s in steps if s["status"] == "error"]
    assert labels == ["check:amount:mismatch", "check:gap:mismatch", "check:quote:mismatch"]
    assert "3 claims not supported" in steps[-1]["output_summary"]


def test_unknown_deal_is_an_error_step():
    steps = verify_rows(_co(), [dict(opportunity_id="ZZZ", amount_usd=1, days_since_last_buyer_touch=1, buyer_quote="")])
    assert steps[0]["label"] == "check:deal:unknown" and steps[0]["status"] == "error"

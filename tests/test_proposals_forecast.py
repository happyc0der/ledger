import pandas as pd

from ledger.forecast import rollup
from ledger.proposals import propose

ROW = dict(opportunity_id="D1", rep="Rep One", win_probability=0.9, amount_usd=1000, issues=[])


def test_commit_excludes_open_semantic_issues():
    clean = dict(ROW)
    flagged = dict(ROW, opportunity_id="D2", issues=[{"key": "k", "type": "M6_zombie"}])
    f = rollup([clean, flagged], backend="llm")
    assert f["team"]["commit"] == 1000 and f["team"]["best_case"] == 1000  # zombie excluded from both
    assert f["excluded"][0]["opportunity_id"] == "D2" and "not measured" in f["calibration"]


def test_muted_issue_no_longer_excludes():
    flagged = dict(ROW, issues=[{"key": "k", "type": "M3_expired_promise"}])
    assert rollup([flagged], states={"k": {"status": "muted"}})["team"]["commit"] == 1000


def test_proposals_are_concrete_and_reversible():
    deal = pd.Series({"expected_close": "2026-10-01", "stage": "Negotiation", "primary_contact": "Priya", "amount": 550, "next_step": ""})
    p = propose({"type": "M6_zombie", "opportunity_id": "D1", "key": "k", "evidence": "we went with Kestrel", "detail": "d"}, deal, {"competitor_name": "Kestrel"})
    assert p.kind == "close_lost" and p.from_value == "Negotiation" and "Kestrel" in p.rationale
    p2 = propose({"type": "M4_timeline_contradiction", "opportunity_id": "D1", "key": "k2", "evidence": "decision in three weeks", "detail": "d"}, deal, {"decision_date": "2026-11-05"})
    assert p2.kind == "update_field" and p2.field == "expected_close" and p2.to_value == "2026-11-05"
    assert propose({"type": "S7_activity_before_creation", "opportunity_id": "D1", "key": "k3", "detail": "d"}, deal, {}) is None

from ledger import audit


def test_empty_run_is_a_finding_not_a_crash(monkeypatch, tmp_path, one_deal):
    from conftest import make_company
    co = make_company([one_deal], [])
    monkeypatch.setattr(audit, "RUNS_DIR", tmp_path)
    (tmp_path / "v1.jsonl").write_text("")
    fs = audit.check_output(co, "v1", partial=False)
    assert fs and fs[0].severity == "high" and "no rows" in fs[0].title

from ledger import decide
from ledger.config import Provider


def test_decision_cache_key_depends_on_model(monkeypatch, tmp_path):
    monkeypatch.setattr(decide, "CACHE_DIR", tmp_path / "llm")
    state = {"deal": {"opportunity_id": "D1"}, "computed": {"amount_usd": 1}}
    monkeypatch.setattr("ledger.config.provider", lambda name=None: Provider("nicrron", "u", "k", "anthropic/claude-sonnet-5-5"))
    a = decide._cache_path(state, "llm")
    monkeypatch.setattr("ledger.config.provider", lambda name=None: Provider("ollama", "u", "k", "qwen3:14b"))
    b = decide._cache_path(state, "llm")
    assert a != b
    assert decide._cache_path(state, "jev") == decide._cache_path(state, "jev")

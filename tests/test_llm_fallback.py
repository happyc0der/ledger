import ledger.llm as llm
from ledger.config import Provider


class _Dead(Exception):
    status_code = 402


class _Overloaded(Exception):
    status_code = 503


class _BadRequest(Exception):
    status_code = 400


def test_metered_provider_failure_falls_back_to_local(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("LLM_FALLBACK", "ollama")
    monkeypatch.setattr(llm, "_openai", lambda p, m, s: (_ for _ in ()).throw(_Dead("credits depleted")))
    monkeypatch.setattr(llm, "_ollama", lambda p, m, s, n: ('{"ok": true}', 5, 3))
    monkeypatch.setattr(llm, "get_provider", lambda name=None: Provider("ollama", "http://localhost:11434", "ollama", "qwen3:14b"))
    monkeypatch.setattr(llm.tracing, "trace_llm", lambda **k: None)
    gem = Provider("gemini", "https://example.invalid", "k", "gemini-x")
    text, parsed = llm.chat([{"role": "user", "content": "hi"}], schema={"type": "object"}, version="t", session_id="t", provider=gem, use_cache=False)
    assert parsed == {"ok": True}


def _wire(monkeypatch, tmp_path, exc):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("LLM_FALLBACK", "ollama")
    monkeypatch.setattr(llm, "_openai", lambda p, m, s: (_ for _ in ()).throw(exc))
    monkeypatch.setattr(llm, "_ollama", lambda p, m, s, n: ('{"ok": true}', 5, 3))
    monkeypatch.setattr(llm, "get_provider", lambda name=None: Provider("ollama", "http://localhost:11434", "ollama", "qwen3:14b"))
    monkeypatch.setattr(llm.tracing, "trace_llm", lambda **k: None)
    return Provider("gemini", "https://example.invalid", "k", "gemini-x")


def test_overloaded_model_5xx_falls_back(monkeypatch, tmp_path):
    gem = _wire(monkeypatch, tmp_path, _Overloaded("model overloaded"))
    _, parsed = llm.chat([{"role": "user", "content": "hi"}], schema={"type": "object"}, version="t", session_id="t", provider=gem, use_cache=False)
    assert parsed == {"ok": True}


def test_our_own_bad_request_surfaces(monkeypatch, tmp_path):
    import pytest
    gem = _wire(monkeypatch, tmp_path, _BadRequest("bad schema"))
    with pytest.raises(_BadRequest):
        llm.chat([{"role": "user", "content": "hi"}], schema={"type": "object"}, version="t", session_id="t", provider=gem, use_cache=False)


def test_nicrron_provider_and_price(monkeypatch, tmp_path):
    import json
    from ledger import config
    monkeypatch.setenv("NICRRON_API_KEY", "sk-af-test")
    p = config.provider("nicrron")
    assert p.base_url == "https://api.nicrron.ai/v1" and p.model == "anthropic/claude-sonnet-5-5"
    monkeypatch.setattr(llm, "_USAGE", tmp_path / "usage.json")
    llm._spend(p, 1_000_000, 100_000)  # $2 in + $1 out at the Sonnet 5.5 rate
    u = json.loads((tmp_path / "usage.json").read_text())["nicrron"]
    assert abs(u["usd"] - 3.0) < 1e-6 and u["calls"] == 1


def test_fallback_answer_is_not_cached_under_primary_key(monkeypatch, tmp_path):
    gem = _wire(monkeypatch, tmp_path, _Dead("credits depleted"))
    msgs = [{"role": "user", "content": "hi"}]
    llm.chat(msgs, schema={"type": "object"}, version="t", session_id="t", provider=gem, use_cache=True)
    primary = tmp_path / f"{llm._key(gem, msgs, {'type': 'object'})}.json"
    assert not primary.exists(), "the local model's answer must not be served as the metered provider's answer next time"
    assert len(list(tmp_path.glob('*.json'))) == 1  # cached once, under the fallback's key


def test_throttle_spaces_requests(monkeypatch):
    import time as _t
    p = Provider("nicrron", "https://example.invalid", "k", "m")
    monkeypatch.setenv("NICRRON_RPM", "2")
    monkeypatch.setattr(llm, "_RATE_STAMPS", {})
    slept = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    base = _t.time()
    monkeypatch.setattr(llm.time, "time", lambda: base)
    llm._throttle(p); llm._throttle(p)
    assert slept == []
    # third call within the minute must wait; simulate the clock jumping past the window after one sleep
    calls = {"n": 0}
    def clock():
        calls["n"] += 1
        return base if calls["n"] < 3 else base + 61
    monkeypatch.setattr(llm.time, "time", clock)
    llm._throttle(p)
    assert slept and slept[0] > 59

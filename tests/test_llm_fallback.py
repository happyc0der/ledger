import ledger.llm as llm
from ledger.config import Provider


class _Dead(Exception):
    status_code = 402


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

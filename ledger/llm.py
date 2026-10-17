"""One chat() for every provider, with a disk cache and PRISM tracing.

Ollama is called through its native API so we can force JSON-schema output and turn
thinking off; Groq/xAI go through the OpenAI protocol with json_object mode and the
schema stated in the system prompt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time

import httpx

from . import tracing
from .config import CACHE_DIR, Provider, provider as get_provider


def _key(p: Provider, messages: list[dict], schema: dict | None) -> str:
    raw = json.dumps([p.name, p.model, messages, schema], sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def _ollama(p: Provider, messages: list[dict], schema: dict | None, num_ctx: int) -> tuple[str, int, int]:
    body = {"model": p.model, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0, "num_ctx": num_ctx}}
    if schema:
        body["format"] = schema
    for attempt in range(2):  # a stalled local generation is retried once
        try:
            r = httpx.post(f"{p.base_url}/api/chat", json=body, timeout=2400)
            r.raise_for_status()
            break
        except httpx.ReadTimeout:
            if attempt:
                raise
    d = r.json()
    return d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0)


# --- spend guard for metered providers -------------------------------------------------
# Conservative $/M-token defaults; override with <PROVIDER>_PRICE_IN / _PRICE_OUT.
_DEFAULT_PRICE = {"gemini": (0.30, 2.50), "xai": (0.20, 0.50), "groq": (0.0, 0.0)}  # gemini = 3.5-flash-lite
# Nicrron prices depend on the routed model ($/M tokens, nicrron.ai/docs/models, 2026-10-17); unknown ids
# are charged at the Sonnet rate so the estimate errs high.
_NICRRON_PRICE = {
    "anthropic/claude-sonnet-5-5": (2.0, 10.0), "anthropic/claude-sonnet-5": (2.0, 10.0),
    "anthropic/claude-haiku-5-5": (0.10, 0.50), "anthropic/claude-opus-5-5": (4.0, 20.0),
    "anthropic/claude-fable-5-1": (10.0, 50.0),
    "openai/gpt-5.5": (5.0, 30.0), "openai/gpt-5.4": (2.5, 15.0), "openai/gpt-5.4-mini": (0.75, 4.5),
    "openai/gpt-5.4-nano": (0.20, 1.25), "openai/gpt-6-sol": (2.0, 10.0), "openai/gpt-6-luna": (0.10, 0.50),
    "openai/gpt-5-mini": (0.25, 2.0), "openai/gpt-4.1-mini": (0.40, 1.60),
}
_DEFAULT_BUDGET = {"nicrron": 200.0}  # event credits; everything else keeps the $2 default
_USAGE = CACHE_DIR.parent / "usage.json"


_USAGE_LOCK = threading.Lock()


def _read_usage() -> dict:
    """Tolerant of a concurrent writer: fall back to the last good copy, never to zero."""
    for path in (_USAGE, _USAGE.with_suffix(".bak")):
        try:
            if path.exists():
                return json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
    return {}


def _spend(p: Provider, tin: int, tout: int) -> None:
    pin, pout = _NICRRON_PRICE.get(p.model, (2.0, 10.0)) if p.name == "nicrron" else _DEFAULT_PRICE.get(p.name, (0.0, 0.0))
    pin = float(os.getenv(f"{p.name.upper()}_PRICE_IN", pin))
    pout = float(os.getenv(f"{p.name.upper()}_PRICE_OUT", pout))
    with _USAGE_LOCK:
        u = _read_usage()
        row = u.setdefault(p.name, {"tokens_in": 0, "tokens_out": 0, "usd": 0.0, "calls": 0})
        row["tokens_in"] += tin; row["tokens_out"] += tout; row["calls"] += 1
        row["usd"] += tin / 1e6 * pin + tout / 1e6 * pout
        tmp = _USAGE.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(u, indent=1))
        if _USAGE.exists():
            try:
                _USAGE.replace(_USAGE.with_suffix(".bak"))
            except OSError:
                pass
        os.replace(tmp, _USAGE)  # atomic: readers see the old or the new file, never a partial one
    budget = float(os.getenv(f"{p.name.upper()}_BUDGET_USD", _DEFAULT_BUDGET.get(p.name, 2.0)))
    if row["usd"] > budget:
        raise RuntimeError(f"{p.name} spend ${row['usd']:.2f} exceeds budget ${budget:.2f}; "
                           f"raise {p.name.upper()}_BUDGET_USD to continue")


def _openai(p: Provider, messages: list[dict], schema: dict | None) -> tuple[str, int, int]:
    from openai import OpenAI
    client = OpenAI(base_url=p.base_url, api_key=p.api_key, timeout=60.0, max_retries=2)  # never hang a run on one call
    kwargs = {}
    if schema:
        # Strict schema where the provider supports it (Gemini, Groq); json_object otherwise.
        kwargs["response_format"] = {"type": "json_schema",
                                     "json_schema": {"name": "out", "schema": schema, "strict": True}}
        messages = [{"role": "system", "content": "Respond with JSON matching this schema exactly:\n"
                     + json.dumps(schema)}] + messages
    try:
        r = client.chat.completions.create(model=p.model, messages=messages, temperature=0, **kwargs)
    except Exception as e:  # provider rejects json_schema → plain JSON mode
        if not schema or "json_schema" not in str(e) and "response_format" not in str(e):
            raise
        kwargs["response_format"] = {"type": "json_object"}
        r = client.chat.completions.create(model=p.model, messages=messages, temperature=0, **kwargs)
    u = r.usage
    tin, tout = getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0
    _spend(p, tin, tout)
    msg = r.choices[0].message if r.choices else None
    return (getattr(msg, "content", None) or ""), tin, tout  # empty/blocked reply → ""


def chat(messages: list[dict], *, schema: dict | None = None, version: str, session_id: str,
         metadata: dict | None = None, provider: Provider | None = None, num_ctx: int = 32768,
         use_cache: bool = True) -> tuple[str, dict | None]:
    """Returns (raw_text, parsed_json_or_None). Cached by provider+model+messages+schema."""
    p = provider or get_provider()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{_key(p, messages, schema)}.json"
    if use_cache and cache.exists():
        hit = json.loads(cache.read_text())
        text, tin, tout, ms, cached = hit["text"], hit["tin"], hit["tout"], hit["ms"], True
    else:
        t0 = time.time()
        try:
            text, tin, tout = _ollama(p, messages, schema, num_ctx) if p.name == "ollama" else _openai(p, messages, schema)
        except Exception as e:  # a dead key, exhausted credits or a rate limit must not stop a run: fall over to the fallback provider
            fb = os.getenv("LLM_FALLBACK", "ollama")
            status = getattr(e, "status_code", None)
            # Fall over on auth/credit/rate-limit, any 5xx (overloaded model), and transport errors.
            # A 4xx we caused (400 bad request, 404 model name, 413 too long) must surface instead.
            recoverable = status in (401, 402, 403, 429) or status is None or status >= 500 or isinstance(e, httpx.HTTPError)
            if p.name == fb or not recoverable:
                raise
            print(f"llm: {p.name}/{p.model} failed ({type(e).__name__} {status or ''}); falling back to {fb}", flush=True)
            p = get_provider(fb)
            text, tin, tout = _ollama(p, messages, schema, num_ctx) if p.name == "ollama" else _openai(p, messages, schema)
        ms, cached = int((time.time() - t0) * 1000), False
        cache.write_text(json.dumps({"text": text, "tin": tin, "tout": tout, "ms": ms}))
    tracing.trace_llm(version=version, model=f"{p.name}/{p.model}", messages=messages, output=text,
                      latency_ms=ms, tokens_in=tin, tokens_out=tout, session_id=session_id,
                      metadata={**(metadata or {}), "cached": cached})
    parsed = None
    if schema:
        try:
            parsed = _parse_json(text)
        except json.JSONDecodeError:
            parsed = None
    return text, parsed

"""One chat() for every provider, with a disk cache and PRISM tracing.

Ollama is called through its native API so we can force JSON-schema output and turn
thinking off; Groq/xAI go through the OpenAI protocol with json_object mode and the
schema stated in the system prompt.
"""
from __future__ import annotations

import hashlib
import json
import re
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
_USAGE = CACHE_DIR.parent / "usage.json"


def _spend(p: Provider, tin: int, tout: int) -> None:
    import os
    pin, pout = _DEFAULT_PRICE.get(p.name, (0.0, 0.0))
    pin = float(os.getenv(f"{p.name.upper()}_PRICE_IN", pin))
    pout = float(os.getenv(f"{p.name.upper()}_PRICE_OUT", pout))
    u = json.loads(_USAGE.read_text()) if _USAGE.exists() else {}
    row = u.setdefault(p.name, {"tokens_in": 0, "tokens_out": 0, "usd": 0.0, "calls": 0})
    row["tokens_in"] += tin; row["tokens_out"] += tout; row["calls"] += 1
    row["usd"] += tin / 1e6 * pin + tout / 1e6 * pout
    _USAGE.write_text(json.dumps(u, indent=1))
    budget = float(os.getenv(f"{p.name.upper()}_BUDGET_USD", 2.0))
    if row["usd"] > budget:
        raise RuntimeError(f"{p.name} spend ${row['usd']:.2f} exceeds budget ${budget:.2f}; "
                           f"raise {p.name.upper()}_BUDGET_USD to continue")


def _openai(p: Provider, messages: list[dict], schema: dict | None) -> tuple[str, int, int]:
    from openai import OpenAI
    client = OpenAI(base_url=p.base_url, api_key=p.api_key)
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
    return r.choices[0].message.content or "", tin, tout


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

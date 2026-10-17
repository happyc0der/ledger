# Nicrron API — what we learned on event day (2026-10-17)

Ledger's model calls run through the Nicrron gateway (`https://api.nicrron.ai/v1`, OpenAI
protocol, model `anthropic/claude-sonnet-5-5` by default; `ledger/config.py` → `nicrron`).
Measured behaviour, so the next team does not rediscover it:

| observation | effect on us | handled in |
|---|---|---|
| **60 requests/min per key** (`429 Rate limit exceeded (60 requests/min)`) | five worker threads at ~3 s/call exceed it; our 429 fallback then silently answered from the local model | client-side limiter at 55 rpm (`_throttle` in `ledger/llm.py`, `NICRRON_RPM` to override) |
| **Default output cap 4,096 tokens**, and a schema-constrained answer that hits the cap comes back as **empty content** (`tout=4096`, `content=""`) rather than truncated text | the naive agent's 30-deal batches were blank; our client cached the blank | explicit `max_tokens` (16,384; `LLM_MAX_TOKENS`); empty replies are never cached |
| Long generations (30-deal batch, ~6k output tokens) returned **502** intermittently | the batch fell back to the local model | 180 s client timeout for the gateway (`LLM_TIMEOUT`); retries by the OpenAI client; fallback stays on, but a fallback answer is cached under its own key and a fallback decision is never cached |
| `response_format: json_schema` is accepted for Claude models (strict schema honoured in our smoke test) | no change | — |
| `/v1/models` lists 87 models with ids as `provider/model`; prices on nicrron.ai/docs/models | spend guard prices per model (`_NICRRON_PRICE`), unknown ids at the Sonnet rate | `ledger/llm.py` |
| Latency on `claude-sonnet-5-5`: 1–4 s for a 2–3k-token extraction, 25–30 s for a 9k-token naive batch | the PRISM "stalled call > 20 s" alert fires on naive batches, which is the behaviour we wanted to catch | PRISM alert rule |

Credits: $260 per participant, expire 2026-10-18 18:00 ET. Spend is logged per call in
`.cache/usage.json` (`nicrron` row).

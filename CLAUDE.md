# Ledger — pipeline review agent (AI × GTM Hackathon, Revenue Intelligence)

See PLAN.md for product, architecture, eval and schedule. Python 3.14 venv at `.venv/`.

## Layout
- `data/company/` demo company built by `scripts/build_company.py`; `ground_truth.csv` is
  hidden from agents — only `ledger/evaluate.py` may read it (via `data.load_truth`).
- `ledger/agent_v1.py` naive agent (kept as-is for the comparison); `ledger/agent_v2.py`
  the real one; `ledger/decide.py` typed decisions (Jev, else local-model fallback);
  `ledger/tools.py` deterministic facts; `ledger/evaluate.py` metrics and verdicts.
- `scripts/run.py v1|v2 [--reps a,b] [--limit N]` → `runs/<version>.jsonl`;
  `scripts/run.py eval v1 v2` → `reports/`.
- Model responses are cached under `.cache/`; delete to force re-inference.
- UI: `.venv/bin/uvicorn ledger.app:app --port 8787` → http://localhost:8787 (reads
  `runs/`; run `scripts/run.py eval v1 v2` first so receipts and Proof have data).

## Inference
No paid credits. `LLM_PROVIDER=ollama` (default, local `qwen3:14b`) | `gemini` (3.5-flash-lite, metered: spend logged to `.cache/usage.json`, hard stop at `GEMINI_BUDGET_USD`, default $2) | `groq` | `xai`;
keys in `.env` (never commit). `DECIDE_BACKEND=jev|llm` overrides auto-detection.

## PRISM tracing
Every model call and every agent run must be traced to PRISM. Wire new code through
`ledger/tracing.py` only:
- model calls go through `ledger.llm.chat(...)`, which calls `tracing.trace_llm` with
  `version`, `session_id` (one per version+rep, e.g. `v2-Darcel_Schlecht`) and metadata;
- each agent run submits `tracing.trajectory(...)` with ordered `tracing.step(...)`
  entries; verifier verdicts are steps named `check:<what>:<match|mismatch|dropped>`;
- agent identity is `agent_id="ledger"`, `agent_name="ledger-<version>"`.
Set `PRISM_DISABLED=1` while iterating (free tier: 100 analyses/day, 100 credits).
Verify with `.venv/bin/python scripts/prism_smoke.py` then
`curl -sS "$PRISM_HOST/api/setup-doctor?project_id=$PRISM_PROJECT_ID" -H "X-PRISMtrace-Key: $PRISM_API_KEY"`
and confirm `live_connected` is true.

# Ledger — the revenue forecast with receipts (AI × Fintech "Money Talks 2", Money Operations)

See PLAN.md for product, architecture, eval and schedule. Python 3.14 venv at `.venv/`.

## Layout
- `data/company/` demo company built by `scripts/build_company.py`; `ground_truth.csv` is
  hidden from agents — only `ledger/evaluate.py` may read it (via `data.load_truth`).
- `ledger/agent_v1.py` naive agent (kept as-is for the comparison); `ledger/agent_v2.py`
  the real one; `ledger/decide.py` typed decisions (Jev, else local-model fallback);
  `ledger/tools.py` deterministic facts; `ledger/evaluate.py` metrics and verdicts.
- `scripts/run.py v1|v2 [--reps a,b] [--limit N]` → `runs/<version>.jsonl`;
  `scripts/run.py eval v1 v2` → `reports/` (uses ground truth: demo/proof only).
- `scripts/run.py audit [--hours N] [--activities path] [--label name]` → `reports/<label>.md`:
  `ledger/audit.py` finds failures WITHOUT ground truth — PRISM guardrail flags traced back to
  data vs agent output, PRISM trajectory rule fails, stated-vs-computed numbers, quote
  existence, catalogue mismatches, data hygiene, calibration smells. When something goes
  wrong, extend the auditor with a check rather than fixing the symptom by hand.
- Any CRM export: `scripts/ingest.py --preset hubspot|salesforce|ledger --deals … --activities … --out data/<name>`
  then `LEDGER_DATA=data/<name> LEDGER_AS_OF=YYYY-MM-DD scripts/run.py v3`. Presets live in
  `ledger/ingest.py` (column candidates, stage map, buying-role map); missing files degrade
  (no catalogue → no scope/arithmetic checks; no contacts → champion from primary_contact).
- Model responses are cached under `.cache/`; delete to force re-inference. A metered provider that
  fails (401/402/403/429/network) falls over to `LLM_FALLBACK` (default `ollama`) mid-run.
- Stage: `./scripts/demo_up.sh` (both UIs, PRISM check, bookmark URLs); DEMO.md has the script;
  docs/SUBMISSION.md the write-up; docs/DAY_OF.md the morning checklist.
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

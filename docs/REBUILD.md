# Rebuilding Ledger from scratch in one day

If the hackathon rules require code written on the day, this is the order that gets to a
provable result by 17:15. Every step names the spec it implements; the specs are prose, not
code. Rehearse it twice before the day.

| when | build | spec | proves |
|---|---|---|---|
| 09:00 | data loader + CRM rules + PRISM smoke trace | `docs/spec/rules.md`, `CLAUDE.md` "PRISM tracing" | `live_connected` true; rules table |
| 10:30 | claim ledger extraction + verifier | `docs/spec/claims.md` | one deal's ledger with quotes; a dropped claim |
| 12:30 | consistency comparison + cross-deal; v3 runner; naive runner | `docs/spec/consistency.md` | issues on the planted deals |
| 14:00 | scorer against `anomalies.csv` | `ledger/score_issues.py` (may be kept as spec) | rules vs naive vs Ledger table |
| 15:00 | FastAPI + one page: list, drawer, receipts, proof | `docs/spec/ui.md` | clickable demo |
| 16:00 | auditor (PRISM flags → attribution), README, FINDINGS, backup video | `docs/spec/audit.md` | the loop, closed |
| 17:15 | submit | | |

Pre-approved inputs (data, not code): `data/company/` (deals, activities, contacts, products,
team, anomalies.csv), `data/templates/`, `.env` with a **fresh** PRISM project's keys.

Day script: `scripts/day.sh` runs make_data → v1 (one rep, PRISM on) → naive → v3 → eval →
issues → audit → UI, in that order, so the PRISM free quota (100 analyses/day) is spent on
the traces the demo shows.

Fresh PRISM project checklist: new project in the dashboard → keys into `.env` →
`scripts/prism_smoke.py` → setup-doctor shows `live_connected: true` → one-rep v3 run →
open Traces, Agent Runs, Guardrails; screenshot each.

# Ledger — system design

Ledger turns a CRM export into a revenue forecast whose every dollar has a receipt. This
document explains what happens, in what order, with what data, and where it can fail. It is
written for someone who has not read the code.

## 1. Problem and constraints

A finance or sales-ops team signs off a forecast built on CRM fields that reps fill in
optimistically. The information that would correct the forecast — "budget frozen until next
year", "we went with a competitor", an auto-reply saying the champion left — sits in free
text that nobody re-reads. Ledger's job is to read that text for every deal, compare what the
*buyer* said against what the CRM *says*, and refuse to show anything it cannot prove.

Constraints that shaped the design:
- **No trust in model output.** A language model may read, never compute or assert. Every
  number is computed in code; every quote must exist verbatim in the record or it is dropped.
- **Weekly, not once.** Runs must be cheap to repeat, diffable, and remember decisions.
- **Any CRM.** Exports differ in columns, stages and who gets credited for an email.
- **Observable.** Every model call and every per-deal decision is traced to PRISM so failures
  are found by the pipeline, not by the user.

## 2. Components

```
 CRM export ──▶ Ingest ──▶ Canonical dataset ──▶ Attribution ──▶ Agent (v3) ──▶ Store ──▶ UI / Digest / Export
  (HubSpot,     presets,    deals · activities    who said it      rules        SQLite     FastAPI + one page
   Salesforce)  stage map   contacts · products   per activity     claim ledger  history    markdown digests
                                                                   verifier      issues     CRM-shaped CSV
                                                                   consistency   state
                                                                   judgement
                                                        ▲                              │
                                                        │            PRISM ◀───────────┘  traces · trajectories · check:* steps
                                                        │              ▲
                                                        └── Auditor ───┘  reads PRISM + outputs + CRM; attributes failures
```

| component | file | responsibility |
|---|---|---|
| Ingest | `ledger/ingest.py`, `scripts/ingest.py` | map a CRM export to canonical CSVs; keep custom stages; derive `history.csv` + `profile.json` from closed deals; refuse exports with no buyer-attributable activity |
| Attribution | `ledger/attribution.py` | resolve a speaker per activity: direction → from-domain → auto-reply → author name → unknown; mark buyer words quoted inside rep notes |
| Rules | `ledger/rules.py` | field-only checks S1–S8 (what CRM alerts can do); the baseline |
| Claim ledger | `ledger/claims.py` | model extracts buyer-stated facts into a fixed schema with verbatim quotes; verifier nulls anything unquoted; dates taken from the record |
| Consistency | `ledger/consistency.py` | code compares ledger vs CRM fields → typed issues M1–M10 with quote, action, evidence grade; cross-deal pass per account |
| Judgement | `ledger/decide.py` | win probability, objection, next action; Jev when a key exists, else structured output from the LLM |
| Calibration | `ledger/calibrate.py` | isotonic regression on (prediction while open → outcome later), held-out Brier |
| Store + history | `ledger/store.py`, `ledger/history.py` | SQLite per dataset: runs, deal snapshots, issues with stable keys, lifecycle state, proposals; diffs between runs |
| Proposals | `ledger/proposals.py` | one reversible CRM edit per finding; approved drafts export in the CRM's own columns |
| Forecast / digest | `ledger/forecast.py`, `ledger/digest.py` | commit / best case from deals with no open issue; Monday notes per rep and manager |
| App | `ledger/app.py`, `ledger/static/index.html` | JSON API + one-page UI: ranked pipeline, receipts, issues, lifecycle, proposals, proof |
| Auditor | `ledger/audit.py` | deterministic checks over PRISM flags/rules, agent output and data; findings with attribution and fix |
| Tracing | `ledger/tracing.py`, `ledger/llm.py` | every model call → PRISM trace; every deal → PRISM trajectory with `check:*` steps; disk cache; spend guard |

## 3. Data model

Canonical dataset (`data/<name>/`, CSV):
- `deals`: opportunity_id, account, product, sales_agent, stage (+ `stage_raw`), amount, created_date, expected_close, primary_contact, last_activity_date, next_step
- `activities`: activity_id, opportunity_id, date, type, author, text, direction, from_addr, to_addr → at load: `speaker`, `speaker_basis`
- `contacts`: opportunity_id, name, title, role (champion | economic_buyer), email
- `products` (list prices), `team` (rep → manager), `history.csv` (closed deals), `profile.json` (learned thresholds), `ledger.json` (RevOps settings)
- Benchmark only, never read by agents: `ground_truth.csv` (outcomes), `anomalies.csv` (planted labels)

Per-deal claim ledger (model output after verification):
`budget_status, decision_timeline, decision_date, economic_buyer, champion_status, competitor_status, competitor_name, product_discussed, units_discussed, total_stated_usd, commitment, last_buyer_promise, last_buyer_promise_date, rep_sentiment_after_last_buyer_message` + `quotes{slot → sentence}`, `grades{slot → A|B|C}`, `dropped[]`.

Issue: `opportunity_id, type (S1–S8 | M1–M10), detail, evidence, severity, action, source, extra, key = sha1(deal|type|evidence anchor)`.

Store (`runs/<dataset>/ledger.db`): `runs`, `deal_snapshots` (stage, amount, close date, contact, p, record_hash, ledger_json), `issues`, `issue_state` (new | acknowledged | muted | resolved), `proposals` (draft | approved | rejected | exported).

## 4. A run, step by step

1. **Load** the dataset; annotate every activity with a speaker. Buyer is never assumed.
2. **Rules** on fields only (past close date, no next step, dormant, blank amount, stalled,
   duplicate, impossible dates, wrong last-activity field).
3. For each deal, **if the record hash matches the previous run, reuse its ledger**; else the
   model fills the claim ledger from the PII-tokenised record.
4. **Verify**: a claim without a verbatim buyer/system quote (or a quoted-buyer span inside
   a rep note) is nulled; dates come from the activity that holds the quote.
5. **Compare** ledger vs CRM → issues with evidence; each check also records pass / fail /
   skipped with a reason ("why not flagged").
6. **Judge**: win probability, objection, next action from the decision model; explanation
   quote verified the same way, dropped if unverifiable.
7. **Cross-deal** pass per account (a contact reported gone on one deal, still primary on another).
8. **Persist** the run; **diff** against the previous one (new / recurring / resolved,
   close-date pushes, Δp, promise age); draft proposals for new findings.
9. **Audit**: read PRISM flags and rule results plus the run's own output; attribute each
   failure to data / agent / guardrail / instrumentation; write `reports/audit_<version>.md`.
10. **Serve**: UI, digests, forecast (commit/best case exclude deals with open issues; the
    strip states whether probabilities are calibrated and on how many outcomes).

## 5. Interfaces

CLI (`scripts/run.py`): `v1 | v2 | v3 | naive` (run), `eval` (outcomes), `issues` (planted
labels or reviews), `audit`, `digest`, `export-approved <preset>`, `agree`, `prism-publish`.
Also `scripts/ingest.py`, `scripts/live.py` (CSV in → findings out, threaded), `scripts/make_data.sh`.

HTTP (`ledger/app.py`): `GET /api/meta`, `/api/deals?version=&show_muted=`, `/api/deal/{id}`,
`/api/history`, `/api/forecast`, `/api/digest?rep=`, `/api/proposals`, `/api/issues`,
`/api/compare`, `/api/precision`; `POST /api/issue/{key}/state`, `/api/proposal/{id}`, `/api/review`.

Environment: `LEDGER_DATA` (dataset dir), `LEDGER_AS_OF` (review date), `LLM_PROVIDER`
(ollama | gemini | groq | xai), `DECIDE_BACKEND` (jev | llm), `PRISM_*`, `*_BUDGET_USD`.

## 6. Failure handling and limits

- **Model returns nothing / malformed**: the slot is null; the deal is scored on rules only; the
  auditor counts it. A whole-run crash cannot lose data: rows are written per rep, the store
  per run.
- **Unverifiable quote**: one retry with a stricter prompt, then dropped and logged as
  `check:quote:dropped`. The naive baseline exists precisely to show what happens without this.
- **Nothing attributable to a buyer**: ingest stops with an explanation rather than running
  and finding nothing.
- **Spend**: every metered call is logged; a provider stops at its budget.
- **Concurrency**: the spend ledger uses a lock and atomic replace; per-deal work is
  independent, so the live path runs reps in a thread pool.
- **Known limits**: one product per deal; English; records over ~24k characters are not yet
  chunked; the fallback decision model is calibrated only once a company has outcome history;
  Jev not yet integrated (waitlist).

## 7. Observability

Every model call is a PRISM trace (agent `ledger-<version>`, one session per rep, metadata
`deal_id`, `role`). Every deal is a trajectory: `crm_query → rules → claim_ledger[:cached] →
check:<type>:fail… → check:summary → decide → check:quote:* → final_answer`, `final_status =
error` when a semantic issue is open. The auditor runs after every agent run, is itself a
trajectory (`ledger-audit`), and writes FINDINGS.md rows when something is fixed.

## 8. Evaluation

Three measurements, kept apart on purpose:
- **Outcomes** (independent): revenue captured in the top-20, Brier and reliability of win
  probabilities, against real win/loss — benchmark data has it hidden; customer data gets it
  as deals close.
- **Planted anomalies** (benchmark only): per-type precision/recall for CRM rules, a naive
  "list the issues" agent and Ledger; false-alarm rate on clean deals.
- **Reviews** (customer data): a manager's ✓/✗ on shown findings → observed precision per
  type with Wilson bounds; the auditor demotes a check the manager keeps rejecting.

Current numbers are in README.md; every adjustment made after a measurement is in FINDINGS.md.

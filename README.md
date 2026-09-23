# Ledger — the pipeline review that shows its receipts

*AI × GTM Hackathon (Block Convey) · Revenue Intelligence track*

A sales manager asks: **"What should my team work on this week?"** Ledger reads the CRM
snapshot and every call note, email and meeting, and answers with a ranked list. For each
deal: a calibrated win probability, the buyer's real objection quoted from the record, and
one specific next action. Every number and quote is checked in code against the CRM before
the manager sees it, and every run is traced in PRISM.

The point of the project is not the agent. It is the proof: the same 228 deals were run
through a naive first version and a verified second version, and both were scored against
what actually happened to those deals.

## The failure nobody planted

We built v1 the way most teams build their first agent: one model call per rep, every deal
in context, and the model does the ranking, the probabilities, the objection, the next step
and the arithmetic. It reads well. PRISM showed it was wrong in ways you could not see from
the output:

- **$109K of pipeline missing.** The CRM spells one product `GTXPro`; the catalogue says
  `GTX Pro`. v1 quietly dropped it from every total. (This is real: the spelling drift is in
  the public dataset we started from.)
- **65 of 228 day-gaps fabricated.** "Days since the buyer last responded" was computed by the
  model, and it counted the rep's voicemails as buyer contact.
- **Overconfidence that costs money.** v1 put 89 deals at ~90% win probability, so its
  "top 20" was just the 20 biggest deals — half of them lost. When v1 says 90%, 79% close.
- **Reads the mood, not the history.** On deals where the buyer raised an objection and then
  resolved it, v1 mostly reported "no objection".

And one failure in *our* pipeline, not the agent's: PRISM's PII guardrail flagged v1 traces
for phone numbers and email addresses. There are none in the source data. The local model we
used to paraphrase the templated notes had invented them — plus a "my sister" and a
"switching from Salesforce". Our fact-checker only verified that original facts survived,
never that nothing was added. Fixed (two-way check, `scripts/paraphrase.py`), re-run, flags gone.

## The fix

v2 changes the architecture, not the prompt:

- **One deal per context.** No cross-deal bleed, no duplicates, no skipped deals.
- **Facts come from code.** Amounts (catalogue-normalised), days since the *buyer* last
  touched the deal, pipeline totals — never from the model.
- **Decisions are typed.** Win probability, objection class and next action are answered
  as probabilities by a decision model (Jev by TypeSafe when a key is present; a
  structured-output fallback otherwise). The language model only extracts the supporting
  quote and writes one sentence.
- **Nothing unverifiable is shown.** A cited quote must exist verbatim in the record or it is
  dropped; every check is a `check:*` step in the PRISM trajectory and a ✓/✗ receipt in the UI.
- **"Disqualify" is a valid answer.**

## Results — same 228 deals, same snapshot, scored against real outcomes

| metric | v1 (naive) | v2 |
|---|---|---|
| Revenue captured in the agent's top 20 (of $113.8K possible) | $59.7K (53%) | **$80.7K (71%)** |
| Pipeline total error | −18% | **0%** |
| Fabricated amounts / day-gaps / quotes | 1 / 65 / 2 | **0 / 0 / 0** |
| Objection accuracy | 79% | **96%** |
| Next-action accuracy | 86% | **99%** |
| Generic "re-engage" actions | 25 | 17 |
| Brier score (lower = better calibrated) | 0.149 | **0.127** |
| Rep-inflated lost deals flagged at risk | 45/48 | **48/48** |

Reliability, v2: its top confidence bin closes at about the rate it states; its bottom bin closes at zero (see the Proof tab for the live table).

**Read the zero honestly.** v2's amounts and day-gaps come from code, so those fabrication
counts are zero by construction — the receipts make that visible, they don't make it
impressive. The quote count is the real one: the model still writes the quote, and in 228
deals it never cited a sentence that wasn't in the record (zero retries, zero drops); on 96
deals it chose to cite nothing. Objection and next-action accuracy are scored against labels
we planted, so treat them as "does it read the buyer", not as independent truth. Revenue
captured and Brier are scored against the real outcomes, which we never touched. Nothing was
tuned against these results; the changes made during the build were bug fixes in our data
pipeline, found through PRISM. Both versions rate
the genuinely unforeseeable losses (buyer said "PO next week", then vanished) above 90% —
correctly, because nothing in the record predicts them. Full table: `reports/v1_v2.md`.

## How PRISM is used

Every model call is a trace (`ledger-v1` / `ledger-v2`, one session per rep) with the
version, deal and role in metadata. Every v2 deal is a trajectory: `crm_query` → `compute`
→ `decide` → `explain` → `check:quote:match|mismatch|dropped` → `check:amount:match` →
`final_answer`. Filtering traces by version is the before/after; opening a v1 trace is where
the missing $66K and the invented day-gaps are visible; the v2 trajectory for the same deal
shows the check steps that stop them. Wiring lives in `ledger/tracing.py`.

## Ledger v3: catching what doesn't add up

A determinism check is table stakes; a rules engine on CRM fields finds past close dates
and blank amounts, and Clari or Gong will sell you that. A revenue agent earns its keep when
the record is *syntactically fine and semantically wrong*: stage says Negotiation, the buyer
said "budget frozen"; the primary contact left the company; "PO next week" was three weeks
ago; the buyer chose a competitor and the deal is still open; a $27K deal in Proposal has no
economic buyer. KC-Bench (2026) shows LLM agents miss exactly these explicit conflicts when
you just ask them to look. So Ledger doesn't ask the model to notice — it asks it to *read*:

1. **Claim ledger (model).** Buyer-stated facts in a fixed schema — budget status, decision
   timeline, economic buyer, champion status, competitor status, units and totals discussed,
   commitment, last promise — each with a verbatim quote. Unknown = null, never inferred.
2. **Verifier (code).** A claim without a verbatim buyer or system quote is nulled; dates come
   from the activity that contains the quote, not from the model.
3. **Consistency (code).** Ledger vs CRM fields, slot by slot, plus a cross-deal pass per
   account (a contact reported gone on one deal, still primary on another).
4. **Judgement (decision model).** Win probability, objection, next action.

### Results on 235 deals with 18 planted anomaly types (149 deals affected, 86 clean)

| | CRM rules | Ledger v3 |
|---|---|---|
| Syntactic (S1–S8: past close date, no next step, dormant, blank amount, stalled, duplicate, impossible dates, wrong last-activity) recall | 99% | 99% |
| **Semantic (M1–M10) recall** | **0%** | **91%** |
| Semantic precision | — | 99% |
| Clean deals falsely flagged | 0 / 86 | **1 / 86** |

Per type (Ledger precision / recall): stage vs buyer 97/97 · contact contradictions 100/88 ·
expired promise 100/78 · timeline contradiction 100/92 · scope vs amount 100/100 · zombie
deal 100/93 · cross-deal contact 100/88 · happy ears 100/93 · missing economic buyer
100/100 · arithmetic 100/100. Full table: `reports/issues.md`; every finding in the UI shows
the CRM value, the buyer's sentence and the recommended action.

**What was adjusted after the first scoring, and what wasn't.** No prompt or model setting
was changed after seeing results. Two comparison bugs were fixed (name matching against
paraphrased first names; a timeline check double-firing on deals already flagged for a past
close date). Three label gaps were closed: contacts who say "I don't own this budget" in a
late stage, a buyer's "I'll ping you when redlines are back" left unanswered for 20+ days,
and "we've paused all vendor onboarding" against a close date weeks away — all true by the
taxonomy's definitions, all verified by reading the evidence, all previously counted as false
positives. The remaining misses are mostly expired promises the model did not record as a
promise ("let me get back to you").

## The auditor: finding failures is the agent's job too

`ledger/audit.py` is the operations-side counterpart: it reads PRISM guardrail flags and rule
results and the agents' own outputs, and writes findings with evidence and attribution (data /
agent / guardrail / instrumentation). It is deterministic and never sees ground truth. It found
the invented phone numbers a paraphrase step had put into the notes — PRISM's PII guardrail
flagged them; the auditor traced them to the data — and the calibration smell in v2's fallback
decision model. `scripts/run.py audit --hours 24` → `reports/audit.md`.

## What is real and what is not

- **Real:** the deals, accounts, products, reps, dates, values and outcomes come from the
  public-domain Maven Analytics "CRM Sales Opportunities" dataset (8,800 B2B deals). We took
  the 228 deals of one team that were open on a snapshot date, shifted every date so the
  snapshot is the Monday after the hackathon, and hid the outcomes from the agent.
- **Real:** the `GTXPro` / `GTX Pro` spelling drift and the blank amounts are in the source data.
- **Synthetic:** the call notes, emails and contacts. The source dataset has no text, and the
  structured fields alone carry almost no win/loss signal (60–65% win rate for every product
  and rep), so we generated a story per deal *conditioned on its real outcome* — 19 archetypes
  including ambiguous ones (won after weeks of silence; lost after a verbal yes; rep says
  "Negotiation", buyer says "budget frozen"). Notes were then paraphrased by a local model so
  they don't share phrasing. The generator and the labels are in `scripts/build_company.py`.
- **Consequence:** objection and next-action accuracy are measured against labels we planted.
  Win/loss and revenue are measured against what really happened.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # PRISM keys; optional GEMINI / GROQ / TYPESAFE keys
./scripts/make_data.sh                         # build -> paraphrase -> plant anomalies (deterministic)
.venv/bin/python scripts/run.py v1             # LLM_PROVIDER=ollama (default) | gemini | groq
.venv/bin/python scripts/run.py v2
.venv/bin/python scripts/run.py v3             # Ledger: rules + claim ledger + consistency + judgement
.venv/bin/python scripts/run.py eval v1 v2     # reports/v1_v2.md + runs/*_verdicts.csv
.venv/bin/python scripts/run.py issues v3      # rules vs Ledger on planted anomalies -> reports/issues.md
.venv/bin/uvicorn ledger.app:app --port 8787   # http://localhost:8787
```

No paid inference is required: the default provider is a local Ollama model. The full
comparison above cost about $0.30 on Gemini Flash-Lite; a spend guard in `ledger/llm.py` stops
metered providers at `GEMINI_BUDGET_USD`.

## Layout

```
data/company/        the demo company (ground_truth.csv is hidden from agents)
ledger/agent_v1.py   naive agent, kept for the comparison
ledger/agent_v2.py   one deal per context, code facts, typed decisions, verified quotes
ledger/agent_v3.py   Ledger: rules + claim ledger + consistency + judgement
ledger/rules.py      the CRM-rules baseline (fields only)
ledger/claims.py     claim ledger extraction + verifier
ledger/consistency.py ledger-vs-CRM comparison, cross-deal checks
ledger/score_issues.py per-type precision/recall vs planted anomalies
ledger/decide.py     Jev / fallback decision layer, one interface
ledger/evaluate.py   metrics, per-deal verdicts (the definition of "fabrication")
ledger/tracing.py    PRISM traces and trajectories
ledger/app.py        FastAPI + one-page UI
scripts/             build_company, paraphrase, run, prism_smoke
```

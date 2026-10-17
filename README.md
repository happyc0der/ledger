# Ledger — the revenue forecast with receipts

*AI × Fintech Hackathon "Money Talks 2" (Block Convey, Oct 17 2026) · Money Operations track*

Every month a finance team signs off a revenue forecast built from a CRM that reps fill in
optimistically: stages that contradict what the buyer actually wrote, close dates that
already passed, deals the buyer lost weeks ago but nobody closed, contacts who left the
company. The forecast inherits all of it. Ledger reads every deal's record — calls, emails,
meetings — into a claim ledger of what the *buyer* said, with verbatim quotes, compares it in
code against the CRM fields, and produces: a commit and best-case number built only from
deals that don't contradict their own record, the specific issues behind every excluded
dollar, draft CRM corrections a human approves, and a Monday digest per rep and manager.
Every number and quote is checked in code before anyone sees it, and every run is traced in
PRISM so the failures are found by the pipeline, not by the CFO.

The point of the project is not the agent. It is the proof: the same deals were run through
a naive first version, a CRM-rules baseline and the verified version, and all were scored
against what actually happened to those deals — because a forecast number is only worth
what its receipts are worth.

## Start here

- **What it is:** a CRM export in, a forecast with receipts out — per deal a win probability, the
  buyer's objection and next action, and every contradiction between the record and the CRM with
  the buyer's verbatim sentence; per team commit / best case with every excluded dollar explained;
  draft CRM corrections a human approves; Monday digests. [How it works](docs/SYSTEM_DESIGN.md).
- **Event-day result (Oct 17, 235 real deals, every model call through Nicrron / Claude Sonnet 5.5):**
  the same model asked to "find the issues" finds 72% of the planted problems, falsely flags 10 of
  86 clean deals and invents 6 numbers; Ledger finds 94%, flags 0, invents 0. Details and the
  three-model comparison are in [Results](#results--same-235-deals-same-snapshot-scored-against-real-outcomes).
- **The three PRISM proofs (Money Operations):** [Sessions → Steps](docs/screenshots/prism_14_session_steps.jpg)
  (a 12-step run per deal) · [an alert firing on a real run](docs/screenshots/prism_15_alert_fired.jpg)
  (model call stalled > 20 s) · [Root Cause](docs/screenshots/prism_17_root_cause.jpg) and
  [PRISM's own narrative](docs/screenshots/prism_16_agent_intelligence.jpg) on the naive agent:
  *"Agent fabricates deal data on pipeline reviews … add guardrails to prevent deal fabrication."*
- **The loop, logged:** 27 failures found through PRISM, the auditor or scoring, each with evidence,
  attribution, fix and re-proof — [FINDINGS.md](FINDINGS.md). 42 items of product feedback for the
  PRISM team — [docs/PRISM_FEEDBACK.md](docs/PRISM_FEEDBACK.md). Gateway lessons — [docs/NICRRON_NOTES.md](docs/NICRRON_NOTES.md).
- **Run it:** [Run it](#run-it) below; demo script [DEMO.md](DEMO.md); submission text
  [docs/SUBMISSION.md](docs/SUBMISSION.md); backup video `docs/video/ledger_demo_backup.mp4`.
- **What is real:** deals, values, dates and outcomes are public CRM data; the notes are synthetic
  and the anomalies planted, disclosed in [What is real and what is not](#what-is-real-and-what-is-not).

## Screenshots

| | |
|---|---|
| ![Pipeline tab with the Dontechi · GTXPro deal open](docs/screenshots/pipeline.png) | ![Warephase · GTXPro: the buyer's arithmetic caught](docs/screenshots/findings.png) |
| Pipeline tab (event run, Claude Sonnet 5.5 via Nicrron): the ranked list with ✓ receipts and issue chips, and Dontechi · GTXPro open — p=10%, four findings with the buyer's sentences, 18 checks run. | Warephase · GTXPro: the buyer wrote "2 units at list, so $14,463"; Ledger's finding says 2 × $4,821 is $9,642, with the quote, the action and a draft CRM correction for a human to approve. |
| ![Proof tab](docs/screenshots/proof.png) | |
| Proof tab, event run: the naive agent vs Ledger on the same 235 deals against real outcomes, and CRM rules vs the naive "find the issues" agent vs Ledger on the planted anomalies (72% / 10 of 86 / 6 invented against 94% / 0 / 0). | |

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

## Results — same 235 deals, same snapshot, scored against real outcomes

| metric | v1 (naive) | v3 (Ledger) |
|---|---|---|
| Revenue captured in the agent's top 20 (of $113.8K possible) | $68.7K (60%) | **$87.6K (77%)** |
| Pipeline total error | −5% | **0%** |
| Fabricated amounts / day-gaps / quotes | 97 | **0** |
| Objection accuracy | 82% | **94%** |
| Next-action accuracy | 87% | **92%** |
| Generic "re-engage" actions | 33 | 22 |
| Brier score (lower = better calibrated) | 0.140 | **0.127** |

Full table (v1, v2, v3): `docs/reports/v1_v2_v3.md`. v2 and v3 share the decision layer, so their
prioritisation numbers are the same; v3 adds the claim ledger and the consistency checks below.

**Read the zero honestly.** v3's amounts and day-gaps come from code, so those fabrication
counts are zero by construction — the receipts make that visible, they don't make it
impressive. The quote count is the real one: the model still writes the quote, and in 228
deals it never cited a sentence that wasn't in the record (zero retries, zero drops); on 96
deals it chose to cite nothing. Objection and next-action accuracy are scored against labels
we planted, so treat them as "does it read the buyer", not as independent truth. Revenue
captured and Brier are scored against the real outcomes, which we never touched. Nothing was
tuned against these results; the changes made during the build were bug fixes in our data
pipeline, found through PRISM. Both versions rate
the genuinely unforeseeable losses (buyer said "PO next week", then vanished) above 90% —
correctly, because nothing in the record predicts them. Full table: `docs/reports/v1_v2.md`.

**Read the commit number honestly.** Commit = probability ≥ 0.7 *and* no open finding. The
second half is a policy, not a prediction, and on this benchmark it does not improve accuracy:
with the rule, 84 deals and $264K of which 87% closed; without it, 139 deals and $404K of which
87% closed; the 55 deals the findings excluded closed at 86%. The CRM's own stage-based commit
closed at 64%. The accuracy lives in the probabilities; the exclusion buys defensibility (every
excluded dollar has a receipt) at the price of $120K that closed. The reason is visible in the
per-type outcomes: the findings that predict loss — stage vs buyer, timeline contradiction,
zombie, happy ears, duplicate (0% win rate) — already pull a deal below 0.7, so what the rule
removes above 0.7 is hygiene (expired promise 63%, missing economic buyer 45%, arithmetic 100%).
We left the rule alone before the demo rather than tune it on the same outcomes; the planned fix
is to learn which finding types a company's own closed deals say are loss-predictive, as the
thresholds already are. FINDINGS.md #27.

### Event day: the same pipeline through Nicrron (Claude Sonnet 5.5)

Money Talks 2 requires model calls through the Nicrron gateway, so on 2026-10-17 the whole
benchmark was re-run on `anthropic/claude-sonnet-5-5` with no prompt changes (`LLM_PROVIDER=nicrron`,
dataset copy `data/company_nicrron`, PRISM sessions tagged `-sonnet`). Same 235 deals, same
snapshot, scored the same way:

| metric | naive v1, Gemini (Sep) | Ledger v3, Gemini (Sep) | naive v1, Sonnet 5.5 (Oct 17) | Ledger v3, Sonnet 5.5 (Oct 17) | Ledger v3, Opus 5.5 (Oct 17) |
|---|---|---|---|---|---|
| Revenue captured in the top 20 (of $113.8K) | 60% | **77%** | 64% | **71%** | 63% |
| Pipeline total error | −5% | **0%** | +1.5% | **0%** | **0%** |
| Fabricated amounts / day-gaps / quotes | 97 | **0** | 6 | **0** | **0** |
| Objection accuracy | 82% | **94%** | 68% | **95%** | 94% |
| Next-action accuracy | 87% | **92%** | 87% | **94%** | 94% |
| Brier score | 0.140 | **0.127** | 0.133 | **0.127** | 0.132 |
| Semantic (M1–M10) recall / precision (naive = "list the issues" agent) | 32% / 62% | **92% / 100%** | 72% / 87% | **94% / 99%** | **95% / 99%** |
| Clean deals falsely flagged | 15 / 86 | **0 / 86** | 10 / 86 | **0 / 86** | **0 / 86** |
| Cost of the v3 run (gateway meter) | ~$0.30 | | ~$6 | | ~$7 |

Three readers, one finding: the **reading** layer improves with the model (semantic recall
92% → 94% → 95%, false alarms 0 on all three), while the **judgement** layer — the same model
asked for a win probability — does not (top-20 revenue 77% → 71% → 63%, Brier flat). A bigger
reader does not buy a better judge; that is why the decision layer is designed to be a
separate, calibrated model (Jev) rather than the reader asked a second question.

A stronger model helps the naive agent a great deal — it fabricates 6 numbers instead of 97
and finds 72% of the semantic issues instead of 32% — and it still invents, still flags 12%
of clean deals, and still hears the buyer's objection wrong a third of the time. The
verification layer transfers unchanged: zero fabrications, zero pipeline error and zero false
alarms on both models, by construction, and the reading layer finds slightly more on Sonnet.
Per-type tables: `docs/reports/issues_sonnet.md`; outcomes: `docs/reports/v1_v3_sonnet.md`. One more
comparison fix was disclosed on the day (FINDINGS.md #23): Sonnet labels a conditional
objection — "won't move forward unless it's on this year's roadmap" — as `commitment=paused`,
which the timeline check had trusted blindly; a `paused` claim now has to be supported by pause
language in its own quote (5 false alarms → 0, recall unchanged, Gemini run unchanged). 
PRISM's trajectory rules pass 17/17 on these runs (they failed two rules before the day's
instrumentation fixes, #18–#19), and the day's gateway lessons are in
[docs/NICRRON_NOTES.md](docs/NICRRON_NOTES.md).

## How PRISM is used

Every model call is a trace (agent `ledger-<version>`, one session per rep and day, provider
and deal in the metadata). Every deal is a run with 12–13 steps — `plan → crm_query → rules →
claim_ledger → verification → check:… → assessment → check:summary → decide → check:quote:… →
final_answer` — so the Sessions → Steps tab shows exactly what happened to a deal and the
`check:*` steps are the receipts. The naive agent's runs carry the same CRM checks over its
answers after the fact, so its fabrications are failed steps PRISM can cluster.

The three Money Operations proofs are live in the dashboard: a run on the Steps tab; three alert
rules scoped to the agent (stalled call > 20 s, guardrail block, empty reply), the first of which
fired on a real run on Oct 17; and Root Cause clusters — the naive agent's runs as failures with a
human-verified cause, Ledger's runs on the same inputs passing 17/17 trajectory rules. PRISM's
Agent Intelligence narrative on the naive agent, unprompted: *"Agent fabricates deal data on
pipeline reviews … add guardrails to prevent deal fabrication."*

PRISM is also read back: the auditor (`ledger/audit.py`) pulls guardrail flags and rule
evaluations after every run and attributes each failure to data, agent, guardrail or
instrumentation. That loop found 27 failures so far (FINDINGS.md), including three in how we
instrumented PRISM itself. Wiring lives in `ledger/tracing.py`; what we would change in PRISM is
in [docs/PRISM_FEEDBACK.md](docs/PRISM_FEEDBACK.md) (42 items).

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

| | CRM rules | naive agent¹ | Ledger v3 |
|---|---|---|---|
| Syntactic (S1–S8: past close date, no next step, dormant, blank amount, stalled, duplicate, impossible dates, wrong last-activity) recall | 99% | 38% | 99% |
| **Semantic (M1–M10) recall** | **0%** | 32% | **92%** |
| Semantic precision | — | 62% | 100% |
| Clean deals falsely flagged | 0 / 86 | 15 / 86 (17%) | **0 / 86** |

¹ The same model (Gemini Flash-Lite), handed 25 deals at a time with the same taxonomy and
asked to list every issue with a quote. It found 0 of 8 cross-deal contact departures and 1
of 43 expired promises, and invented issues on 17% of clean deals — the KC-Bench result,
reproduced. Ledger uses the same model; the difference is that it only *reads*, and code
does the comparing.

Per type (Ledger precision / recall): stage vs buyer 97/97 · contact contradictions 100/88 · expired promise 100/91 · timeline contradiction 100/92 · scope vs amount 100/100 · zombie deal 100/93 · cross-deal contact 100/88 · happy ears 100/93 · missing economic buyer 100/100 · arithmetic 100/100. Full table: `docs/reports/issues.md`; every finding in the UI shows
the CRM value, the buyer's sentence and the recommended action.

**What was adjusted after the first scoring, and what wasn't.** No prompt or model setting
was changed after seeing results. Three comparison bugs were fixed (name matching against
paraphrased first names; a timeline check double-firing on deals already flagged for a past
close date; a buyer "leaning toward MG Special" — our own product — counted as leaning to a
competitor, which was the single remaining false alarm). Three label gaps were closed: contacts who say "I don't own this budget" in a
late stage, a buyer's "I'll ping you when redlines are back" or "I'll try to get time with
her" left unanswered for 14+ days, and "we've paused all vendor onboarding" against a close
date weeks away — all true by the taxonomy's definitions, all verified by reading the
evidence, all previously counted as false positives. Closing them also added cases the
model misses, which is why recall is 92% and not higher. A fourth comparison fix followed the
clean re-run: an economic buyer recorded as "finance" — a department — must not be compared to a
person. A fifth came from running a second model on the day: a `paused` commitment only counts when its quote
reads like a pause (FINDINGS.md #23).

Every failure found during the build, its PRISM evidence, attribution and fix is in
[FINDINGS.md](FINDINGS.md).

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
cp .env.example .env            # PRISM keys; NICRRON_API_KEY for the gateway; optional GEMINI / GROQ / TYPESAFE
./scripts/make_data.sh                                   # build -> paraphrase -> plant anomalies (deterministic)
export LLM_PROVIDER=nicrron                              # or ollama (local, free) | gemini | groq | xai
.venv/bin/python scripts/run.py v3 --workers 5           # Ledger: rules + claim ledger + consistency + judgement
.venv/bin/python scripts/run.py v1 --workers 2           # the naive agent, same model
.venv/bin/python scripts/run.py naive --workers 5        # the "list the issues" agent
.venv/bin/python scripts/run.py eval v1 v3               # against real outcomes -> reports/
.venv/bin/python scripts/run.py issues naive v3          # rules vs naive vs Ledger on planted anomalies -> reports/issues.md
./scripts/demo_up.sh                                     # three UIs (:8787 event run, :8788 live, :8789 Gemini) + checks
.venv/bin/python scripts/live.py --preset hubspot --deals data/templates/hubspot_deals.csv \
  --activities data/templates/hubspot_engagements.csv --contacts data/templates/hubspot_contacts.csv \
  --products data/company/products.csv --as-of 2026-10-19   # an editable export -> findings in ~12 s
```

`LEDGER_DATA=data/<copy>` runs against another dataset directory (the per-model runs above used
copies of `data/company`). Cost of a full 235-deal run: about $6 on Claude Sonnet 5.5 through
Nicrron, about $0.30 on Gemini Flash-Lite, $0 on a local model (times in the table above); a
weekly re-run costs cents because unchanged records reuse their ledger. A spend guard stops
every metered provider at `<PROVIDER>_BUDGET_USD`. The scored tables referenced in this README
are committed under [docs/reports/](docs/reports/).

## On data we did not write: 150 SaaS sales conversations with real outcomes

The benchmark above uses notes we generated. To see what Ledger does on records that are
not ours, `scripts/adapt_saas.py` turns the public `DeepMostInnovations/saas-sales-conversations`
dataset (multi-turn buyer/rep conversations over sms, chat, email and calls; personas; a real
converted/not-converted label) into a Ledger dataset: 150 open deals, 550 closed deals as
history. No anomalies are planted, so only outcomes and hand review can score it.

What held: **0 fabrications**, pipeline total exact, 56 model claims dropped by the verifier
because no quote supported them, and the agent's top-20 captured **85%** of the closable
revenue. The semantic findings read right on inspection — *"I still need to convince my
boss"* → contact lacks authority; *"feels like a lot to commit to right now"* against a
Proposal stage; *"I need to think it over"* 25 days ago and nothing since → expired promise —
and 8 of the 10 inspected flagged deals went on to lose.

What did not hold, and the auditor caught both without being told: the fallback **judgement
layer does not transfer**. Its win probabilities bunch in 0.2–0.6 (Brier 0.226 against a 50%
base rate — barely better than guessing) and its objection classifier collapsed to "budget"
on 95% of deals (`degenerate_classifier` finding). And `M9_missing_economic_buyer` fired on
79% of deals because this CRM holds one contact per deal (`saturated_check` finding — the
fix is a setting, not a model). This is the measured case for a calibrated decision model
(Jev) or outcome-based calibration before anyone trusts the probabilities on a new company;
the reading and verifying layers carried over, the judging layer did not.

**The reading model matters, and the verifier shows exactly how.** A second batch (60 deals,
six companies) run on a local 12B model (`gemma4:12b` on a GPU box, free) extracted 2.0
filled slots and 1.8 verified quotes per deal against 3.0 and 2.3 for Gemini Flash-Lite, had
unsupported claims dropped at 2.5× the rate (≈1 per deal vs ≈0.4), and produced **zero**
buyer-words findings where Gemini found ten. The verifier guarantees that nothing false is
shown; it cannot manufacture recall. So "runs on a free local model" is true for the
pipeline and the number has to be stated per model. On the planted-anomaly benchmark itself,
the same 235 deals on `gemma4:12b` (free, on a consumer GPU) score **82% semantic recall /
91% precision / 1 of 86 clean deals flagged** against Gemini Flash-Lite's 92% / 100% / 0 —
syntactic recall identical (99%), fabrications still 0, revenue in the top-20 73% vs 77%.
The architecture carries most of the result; the reading model sets the ceiling.

## Week after week

Ledger is built to be run every Monday, not once:

- **History.** Every run is stored (`runs/<dataset>/ledger.db`); the UI shows what is *new
  since last review*, *recurring* (with first-seen date), *resolved*, close-date pushes and
  win-probability deltas. Unchanged records reuse last week's claim ledger, so a weekly run
  costs cents.
- **Lifecycle.** Each finding has a stable identity; a manager can acknowledge, mute or
  resolve it, and muted findings stop counting against the forecast.
- **Draft CRM updates, human-approved.** Findings become concrete edits (move the close date
  to the buyer's stated decision date; close-lost with the competitor as reason; replace the
  departed primary contact; a task for the rep). Nothing is written to the CRM: approved
  drafts export as an import file in the CRM's own column names (`scripts/run.py export-approved hubspot`).
- **Forecast.** Commit and best case are built only from deals with no open semantic issue,
  and the strip says whether the probabilities behind them are calibrated.
- **Digests.** `scripts/run.py digest` writes a Monday note per rep and one for the manager:
  new issues with the buyer's sentence and the action, promises past due, pushes, resolved.
- **Reviews.** ✓/✗ on any finding records a verdict; the Proof tab shows observed precision
  per type with 95% bounds, and the auditor flags a check the manager keeps rejecting.
- **Checks run.** Every deal shows which checks passed, failed or were skipped and why —
  "why wasn't this flagged" is answered, not guessed.
- **Privacy.** Emails and phone numbers are tokenised before any prompt and restored only
  in verified quotes.
- **Thresholds are the company's, not ours.** Win rate and cycle length come from the
  company's own closed deals (`profile.json`; for the demo company, 6,711 of them); everything
  else is in `ledger.json`. The UI header says where each number came from.
- **Extraction stability.** `scripts/run.py agree` re-extracts a sample uncached and reports
  per-slot agreement (84–100% on a 25-deal sample; `reports/agreement.md`).

<p align="center"><img src="docs/screenshots/01_pipeline_v3.png" width="820" alt="Ledger: ranked pipeline with receipts, a deal's four findings each with the buyer's sentence"><br>
<img src="docs/screenshots/prism_10_v3_run_timeline_checks.jpg" width="400" alt="PRISM: a Ledger run as a timeline of check steps"> <img src="docs/screenshots/prism_03_trace_pii_flag.jpg" width="400" alt="PRISM: the v1 trace with the PII guardrail flag that exposed our data bug"></p>

## How it works

[docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) — components, data model, a run step by step,
interfaces, failure handling, observability and evaluation, written for someone who has not
read the code. [docs/architecture.svg](docs/architecture.svg) is the one-picture version. Screenshots of the UI
and of PRISM (traces with the PII flags, agent runs with `check:*` steps, the judge's
evaluation, the auditor's run) are in `docs/screenshots/`; a 90-second captioned backup
video is `docs/video/ledger_demo_backup.mp4`. Feedback for the PRISM team, with evidence, is in
[docs/PRISM_FEEDBACK.md](docs/PRISM_FEEDBACK.md).

## Status and what's still missing

**Working today:** everything above — ingest, claim ledger, consistency checks, rules
baseline, judgement, history/lifecycle, proposals, forecast, digests, reviews, auditor, UI,
tests (`pytest`), and the live run on a HubSpot-shaped CSV.

**Not yet integrated: Jev (TypeSafe AI, System One model).** The judgement layer — win
probability, objection, next action — currently runs on a *fallback*: structured output from
the same language model that reads the notes. Measured on the 235 real outcomes it is better
than expected — Brier 0.128 against 0.237 for guessing the base rate, and its top bin (stated
0.88) closes at 0.86 — but its low bins are off, and it is one model doing two jobs. Ledger
now **self-calibrates** from the company's own outcomes (`ledger/calibrate.py`: isotonic
regression on predictions made while deals were open, scored with a held-out Brier — 0.117
here; the forecast strip shows the number). Jev is a decision model that returns calibrated
probabilities for typed questions instead of generating text; it is the intended judgement
layer and the comparison we want to publish. Access is on TypeSafe's waitlist.

What changes when the key arrives (`TYPESAFE_API_KEY` in `.env`; `ledger/decide.py` already
has the Jev backend and switches automatically):
1. Re-run v3 (ledgers are reused, so only judgements recompute) and re-evaluate: Brier score
   and reliability against the 235 real outcomes, Jev vs the fallback. If the 80% bin closes
   at ~80%, the forecast becomes defensible and the strip flips to "✓ calibrated".
2. Add a second reader for the typed ledger slots (budget, champion, competitor, commitment,
   rep tone) so per-slot confidence comes from two different models agreeing, not one model
   re-run.
3. Cost is negligible: $0.042 per million input tokens, output free — about $0.015 for a full
   235-deal run, ~$6/year for a 2,000-deal company run weekly. Details and steps: PLAN.md,
   "Jev 1.13 plan".

**Done on event day:** every model call through Nicrron with a client-side rate limiter and
streaming; three PRISM alert rules scoped to the agent (stalled call, guardrail block, empty
reply), one fired on a real run; Root Cause clusters with human-verified causes; the naive
agent's fabrications visible in PRISM as failed check steps; the commit rule measured against
outcomes (#27).

**Also open:** a run on a real customer export (the only test that matters), learning the commit
exclusion set from a company's closed deals (#27), chunking for very long records, and the
forecast's judgement layer (Jev, above).

## Bring your own pipeline

```bash
.venv/bin/python scripts/ingest.py --preset hubspot \
    --deals ~/Downloads/hubspot-deals.csv --activities ~/Downloads/hubspot-engagements.csv \
    --contacts ~/Downloads/hubspot-contacts.csv --out data/acme --company "Acme"
LEDGER_DATA=data/acme LEDGER_AS_OF=2026-10-19 .venv/bin/python scripts/run.py v3
LEDGER_DATA=data/acme .venv/bin/uvicorn ledger.app:app --port 8787
```

`ledger/ingest.py` maps HubSpot and Salesforce export columns, stage codes and buying roles
onto Ledger's canonical files; `--mapping overrides.json` handles custom fields. Closed deals
go to `history.csv` and, with 30+ of them, produce `profile.json` — the company's own win rate
and cycle length replace the defaults. Custom stages are kept (with `stage_raw`), not dropped.
**Who said it** is resolved per activity from the strongest evidence available — email
direction, from-address domain, auto-reply patterns, then author name — and *unknown is never
buyer*; ingest refuses an export where nothing can be attributed to a buyer, because Ledger
would find nothing and say nothing. Missing inputs degrade honestly: no product catalogue means
no scope/arithmetic checks; no contacts file means the champion is the deal's primary contact.
`ingest_report.json` says which columns were used, the attribution counts and any unmapped stage.

For a first look: `scripts/live.py --preset hubspot --deals data/templates/hubspot_deals.csv
--activities data/templates/hubspot_engagements.csv --contacts data/templates/hubspot_contacts.csv
--products data/company/products.csv` runs an 8-deal export end to end in under a minute.

## Layout

```
data/company/            the demo company (ground_truth.csv is hidden from agents); company_nicrron/, company_opus/,
                         company_mac/, company_msi/ are copies for the per-model runs (ignored); live/ the HubSpot template run
data/templates/          the 8-deal HubSpot-shaped CSVs a judge can edit
ledger/ingest.py         HubSpot / Salesforce presets → canonical CSVs, learned thresholds, attribution report
ledger/attribution.py    who said what: direction → from-domain → auto-reply → author → unknown (never buyer by default)
ledger/rules.py          the CRM-rules baseline (fields only, S1–S8)
ledger/claims.py         claim ledger extraction + verifier (verbatim quotes, evidence grades, PII tokens)
ledger/consistency.py    ledger-vs-CRM comparison (M1–M10), cross-deal, checks with reasons
ledger/decide.py         judgement: Jev when a key exists, else structured output; cache keyed by model
ledger/calibrate.py      isotonic self-calibration from outcomes
ledger/agent_v3.py       Ledger: rules → ledger → verify → compare → judge → PRISM run with check:* steps
ledger/agent_v1.py       naive agent (one context, no tools) with post-hoc CRM checks recorded for PRISM
ledger/agent_naive_issues.py  the "list the issues" agent for the planted-anomaly table
ledger/store.py history.py proposals.py forecast.py digest.py   runs, diffs, lifecycle, draft corrections, roll-up, digests
ledger/audit.py          the auditor: PRISM flags/rules + outputs + data → attributed findings
ledger/llm.py tracing.py providers (ollama | nicrron | gemini | groq | xai), cache, spend guard, rate limiter; PRISM traces/runs
ledger/evaluate.py score_issues.py   outcomes metrics (the definition of "fabrication"); per-type precision/recall
ledger/app.py static/    FastAPI + one-page UI
scripts/run.py           v1|v3|naive|eval|issues|audit|digest|export-approved|prism-publish ; live.py ; ingest.py ; demo_up.sh ; make_video.py
docs/                    SYSTEM_DESIGN, SUBMISSION, DEMO (root), DAY_OF, NICRRON_NOTES, PRISM_FEEDBACK, spec/, screenshots/, video/
tests/                   45 tests, no model calls
```

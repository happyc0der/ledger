# Ledger — pipeline review agent (revised 2026-09-23)

AI × GTM Hackathon (Block Convey), Revenue Intelligence track, **Sat 2026-10-17** (postponed from 09-26 on 09-23; "bigger, more partners").
"The pipeline review that shows its receipts."

## 0. What changed in this revision
- **No Claude credits.** Language layer runs on free inference: Groq free tier for
  speed, local Ollama (`qwen3:14b`, already installed) as the unlimited/offline fallback.
  Optional: xAI's $25 sign-up credit if we want a stronger model on demo day.
- **Jev is the decision layer** (win probability, objection class, next action) via a
  direct TypeSafe key — it is *not* on OpenRouter as of 2026-09-23. Until the key
  arrives, the same interface is served by structured output from the local model.
- Everything is OpenAI-compatible, so one client with a `base_url` switch covers
  Groq / Ollama / xAI. PRISM tracing is done by hand with `trace_llm` + trajectories.

## 1. Product
A sales manager asks: "What should my team work on this week?" The agent reads the CRM
snapshot and every call note/email, and returns a ranked list. Per deal: calibrated win
probability, the buyer's real objection quoted from the record, one specific next
action. Every number and quote is checked in code against the CRM before the manager
sees it; every run is traced in PRISM. The demo proves, on deals whose real outcomes are
known, that v2 prioritises better and is honest about its confidence.

## 2. Demo company
`data/company/` — Vireo Systems (from public-domain Maven CRM data, dates shifted so the
snapshot is Monday 2026-10-19). Melvin Marxen's team: 5 reps, 228 open deals, 672
activities. Real later outcomes hidden in `ground_truth.csv`; notes conditioned on the
outcome via 11 archetypes → ground truth for outcome, objection class and next action.
Data-native traps: `GTXPro` vs `GTX Pro` (65 deals, ~$313K), 42 blank amounts, 56% of
lost deals with rep-inflated stages, 29 multi-deal accounts, "Left VM ×3" inflating
last_activity_date, quiet-but-winning late-stage deals.

## 3. Architecture
```
manager ──▶ FastAPI + one-page UI
                │
        Agent (v1 | v2) ── every model/tool call → PRISM (trace_llm + trajectory)
          │           │
   LANGUAGE           DECISIONS (v2)
   Groq free /        Jev: noul(win?) · choice(objection) · choice(next action)
   Ollama qwen3:14b   fallback: local model structured output, same interface
          │
       Verifier (pure code): amounts, dates, stage, product price, quote-exists
          │
   PRISM steps  check:crm:match | check:crm:mismatch  + metadata {version, deal, verdict}
```
**v1 (naive):** one call per rep, all deals in context, model does ranking, probability,
objection, next step, arithmetic. No tools, no verifier.
**v2:** one deal per context; code tools for pipeline math, days-since-*buyer*-touch,
normalised product lookup; Jev answers the three typed questions with probabilities;
language model extracts the supporting quote + writes rationale; verifier rejects
unsourced claims; "disqualify" is a first-class answer; probabilities anchored to the
63% base rate.

## 4. Evaluation (computed in code from ground_truth.csv, same 228 deals both versions)
| Metric | Judge's question |
|---|---|
| Revenue captured in top-20 ($ that actually closed) | did it point my team at the money |
| Brier score + reliability table (stated p vs real win rate) | when it says 80%, does 80% close |
| Objection accuracy vs planted class | does it hear the buyer |
| Next-action accuracy; count of generic "follow up" | is the advice specific |
| Fabrications: cited amounts/dates/stages/quotes not in the CRM | can I trust a line of it |
| Pipeline total error (GTXPro trap) | is the number on the slide right |
Every per-deal verdict → PRISM trajectory step + trace metadata. Filter by version on stage.

## 5. Inference providers
| Role | Primary | Fallback | Notes |
|---|---|---|---|
| Language | Groq free: `qwen/qwen3.8-27b` (1k req/day) | Ollama `qwen3:14b` (unlimited, ~3s/deal) | one OpenAI-compatible client |
| Decisions | Jev (`typesafe-sdk`) | local model, JSON schema | same `decide()` interface |
| Optional | xAI $25 credit | — | only if Groq quota bites on Saturday |
Cache every model response by (version, deal, prompt hash) so re-runs are free/instant.

## 6. PRISM
SDK 0.5.0. `trace_llm` per model call (model name = provider/model), tool + Jev calls as
trajectory steps, one session per (version, rep). Agents `ledger-v1` / `ledger-v2`.
Free tier: 100 auto-analyses/day, 100 credits → practice project now, fresh project Sat.
Ask hosts for Builder tier (Annotations). On stage: Traces filtered by version → a v1
failing trace → Root Cause → same deal in v2 with `check:crm:match`.

## 7. Schedule (3-week runway)
- **Wk 1 (Sep 23–27): make it work.** v1 + v2 end-to-end on local model, evaluator,
  PRISM wired, Groq + TypeSafe keys. Full 228×2 comparison table. Paraphrase pass over
  the templated notes with the local model so 228 deals read like 228 reps.
- **Wk 2 (Sep 28–Oct 4): make it right.** Jev live; verifier hardened; reliability plot;
  FastAPI + one-page UI; README with "what is real and what is not". Watch Discord for
  new partners/tracks and adapt (a CRM partner → load from their sandbox instead of CSV).
- **Wk 3 (Oct 5–11): make it convincing.** Demo script, backup video, dry-run in front of
  someone in sales; fix what confuses them. Fresh PRISM project for the day.
- **Oct 12–16:** freeze features; rehearse the Saturday rebuild order twice.
- **Sat Oct 17:** §8 order; submit by 17:15.

## 8. Saturday build order (if code must be rebuilt from scratch)
09:00 loader/tools/v1/PRISM → 11:00 run v1, eval, screenshot PRISM failures →
12:30 v2 → 15:00 run v2, comparison → 16:00 UI/README/video → 17:15 submit.

## 9. Demo script (3 min)
1. Problem in a manager's words (20s). 2. v1: confident, wrong — PRISM trace: missing
$313K, lost deal ranked #2 on rep-set stage, invented quote (40s). 3. The fix (30s).
4. Same 228 deals: revenue-in-top-20, Brier, fabrications→0, reliability table; PRISM
v1 vs v2 (60s). 5. Live: click a deal, buyer quote, one action (30s).
6. "If a pipeline review can't show its receipts, it's a guess with a nice UI."

## 10. Ask in Discord
Rubric + judges · pre-written code policy · Builder-tier PRISM · partner credits ·
submission format + demo length.

---

# Revision 3 (2026-09-23): the agent must catch what doesn't make sense

## Why the current story is not enough
Everything v2 catches today is caught by determinism: amounts, day-gaps, quotes, product
spelling. A RevOps checklist or a Clari "deal warning" rule does the same on CRM fields
(past close date, no next step, dormant 30+ days, stage > 2× average, amount missing past
qualification, duplicate open deals on one account, close date pushed >3×). That is the
floor, not the product. A revenue agent earns its keep when the data is *syntactically fine
and semantically wrong*: the stage says Negotiation, the buyer said "budget frozen"; the
primary contact left the company; "PO next week" was three weeks ago; the deal is for one
unit but the buyer is talking about two sites; the buyer already chose a competitor and the
deal is still open. And it must say what is *missing*: no economic buyer on a $27K deal in
Proposal, no timeline, no next step.

Research: KC-Bench (arXiv 2609.03588) shows LLM agents "frequently fail to notice explicit
conflicts" between user-provided data and system records even when they are obvious side
by side. Its design lessons: explicit comparison mechanisms, mandatory cross-checking, safe
defaults toward flagging. That is the architecture below, and it is also why v1 (ask the
model "find the issues") will fail in a measurable way.

## The idea: a claim ledger per deal
1. **Extract (model, typed).** From the record, fill a fixed schema of *buyer-stated facts*,
   each with a verbatim quote and date: budget status, decision timeline, economic buyer
   named, champion status (active / left / unknown), competitor status (none / evaluating /
   chosen), product & quantity discussed, commitment level (none / verbal / PO in flight),
   last buyer promise (what + when). Missing = null, never guessed.
2. **Compare (code).** Field by field against the CRM: stage, amount, product,
   expected_close, primary contact & economic buyer, last_activity_date, activities' dates.
   Each mismatch is a typed contradiction with the CRM value, the buyer quote, and the date.
3. **Missing (code).** Required slots per stage (MEDDPICC-lite): past Proposal → economic
   buyer, timeline, next step; past Negotiation → commitment evidence. Empty slot = finding.
4. **Verify (code).** Every quote must exist in the record; every date must be inside the
   deal's lifetime; otherwise the finding is dropped and logged to PRISM as check:*:dropped.
5. **Judge (decision model).** Given contradictions + gaps, the existing v2 questions: win
   probability, objection, next action, plus "should this deal be closed-lost / disqualified
   now?"

The model reads; code compares; every finding carries a receipt. Same principle as v2,
pushed one level up: from numbers to meaning.

## Anomaly taxonomy (planted in the generator, labelled in ground truth)
Syntactic (rules should catch; the Clari floor):
  S1 expected_close in the past · S2 no next step past Qualification · S3 dormant >30d ·
  S4 amount blank past Qualification · S5 stage > 2× typical duration · S6 duplicate open
  deal on same account+product · S7 activity dated before deal creation · S8 last_activity
  field ≠ activities
Semantic (rules cannot; the agent must):
  M1 stage contradicts buyer words (Negotiation vs "budget frozen"/"chose competitor")
  M2 contact contradiction: champion left (auto-reply) but still primary; econ buyer in
     notes ≠ CRM econ buyer; junior title but "she owns the budget"
  M3 expired promise: "PO next week" dated >14d ago, nothing since
  M4 timeline contradiction: expected_close before the buyer's stated decision date
  M5 amount/scope contradiction: buyer discusses two sites / phased 60-40 / a different
     product; CRM amount is one unit of the deal product
  M6 zombie: buyer wrote "we went with X" and the deal is still open
  M7 cross-deal: auto-reply on deal A says the contact left; deal B at the same account
     still lists them as primary
  M8 happy ears: rep note positive after a buyer note that pauses/declines
  M9 missing: no economic buyer / no timeline / no next step where the stage requires it
  M10 quantity/price arithmetic in notes ("3 units at list = $X") that doesn't match amount
Clean deals: ~60%. Some deals carry two anomalies. Some anomalies are near-misses (buyer
says "decision in Q1" and expected_close is in Q1 → not a contradiction) to measure false
positives, which is where "confident-looking noise" comes from.

## Metrics (all against planted labels; outcomes stay for the revenue/Brier story)
- Per-type precision / recall / F1, and overall, for three systems:
  **v1** one prompt per rep: "list every issue you see" (the naive agent; expect KC-Bench
  behaviour — misses explicit conflicts, invents others);
  **rules** deterministic only (the Clari floor; expect S1–S8 ≈ perfect, M1–M10 ≈ 0);
  **v3** claim ledger + code comparison + verifier (+ Jev or fallback for judgement).
- False-positive rate on clean deals (the manager's trust metric).
- Evidence validity: share of findings whose quote exists and whose date is consistent.
- "Actionable missing": recall on M9.
- Existing: revenue-in-top-20, Brier, fabrications (unchanged).

## Demo shape
"Here are 228 deals. 40% of them have something wrong that the CRM fields can't show you.
A rules engine finds the easy half. The naive agent finds a third and invents a few. Ledger
finds X% with a quote for every one and Y false alarms — and for each, says what to do."
Then click a deal: CRM says Negotiation, $5,482, close Nov 12, contact Priya. Ledger:
"Priya left (auto-reply, Oct 2). Buyer promised a PO on Sep 29; nothing since (20 days).
No economic buyer identified. → multithread to Daniel Kowalski or disqualify."

## Build plan (fits the 3-week runway)
Wk 2a: anomaly generator + labels; rules baseline (extend audit.py checks S1–S8 to per-deal
       findings); extraction schema + prompts; comparison + verifier; metrics.
Wk 2b: v1 "find issues" baseline; v3 full run; UI "Issues" column + drawer section; PRISM
       steps check:consistency:<type>:<pass|fail|dropped>.
Wk 3:  Jev for the typed judgement if the key arrives; README/DEMO rewrite; rehearsal.
Cost: extraction ≈ 2k tokens/deal → ~$0.15 per full run on flash-lite.

Sources: KC-Bench arXiv 2609.03588; fullstackgtm CRM audit checklist (27 checks); crono.one
pipeline hygiene (four-field weekly audit); Gong deal warnings (engagement, single-thread,
stalled, pricing); AskElephant/vonlabs on combining signals before escalating.

---

# Jev 1.13 plan (2026-09-24)

Pricing: $0.042 / M input tokens, output free (docs; confirm no per-request minimum). Access:
direct TypeSafe key (OpenRouter's jev-1.13 page is a placeholder — not in their model list).

Measured on our records: decision request ≈ 290 tokens of deal state + 360 of questions.
Per full 235-deal run: decisions $0.0063; + typed-slot second reader $0.0145. All hackathon
prep ≈ $0.60; $2 ≈ 138 full runs. Production 2,000 deals weekly, both layers: $0.12/week.

1. **Decision layer** (already wired in `decide._jev`): win prob (Noul), objection + next
   action (Choice). Proof = Brier + reliability vs real outcomes, against the fallback the
   auditor flags as overconfident. Forecast strip flips from "⚠ uncalibrated" to "✓".
   Steps: key in `.env` → `run.py v3` (ledgers reused) → `eval v1 v2 v3` → README/DEMO
   numbers → FINDINGS row 10 closed. Add `jev` to the spend ledger with `TYPESAFE_BUDGET_USD`.
2. **Second reader** (`ledger/jev_reader.py`): typed ledger slots (budget, champion,
   competitor, commitment, rep tone) as Choice with probabilities from the raw record; per-slot
   agreement with the LLM ledger → confidence on findings; disagreement → auditor finding.
   `run.py agree --jev`. Quotes stay with the LLM (Jev does not generate text).
3. **Live-demo latency**: decisions in <1 s; extraction on Gemini remains the floor.
Not planned: Jev pre-screening to skip extraction (ledger reuse already covers unchanged records).

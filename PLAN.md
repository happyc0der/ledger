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

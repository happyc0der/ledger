# PRISM feedback log

Running notes for the conversation with Block Convey's CEO. Everything here was observed
while building Ledger (Sep 21 – Oct 16, 2026; ~3,700 traces, ~1,000 trajectories, free tier
then a 14-day Growth trial from Oct 15). Each item says what happened, why it mattered, and
what would have helped. Trace ids refer to project `98b924d6…`.

## What earned its place

1. **A guardrail found a bug in my data pipeline, not my agent.** The PII/PHI rule flagged
   v1 traces (`35c3e334…`, `2a6b8387…`) for phone numbers and emails. None existed in the
   source data — a paraphrase step had invented them. Without the flag I'd have demoed on
   contaminated data. This became the centrepiece of the demo (FINDINGS.md row 4).
2. **The read API is good enough to build on.** `/api/traces/export`, `/api/traces/{id}`
   (with `guardrail_flags[].matched_text`), `/api/trajectories/{id}/evaluation` (per-rule
   evidence) and `/api/sessions` let me write an auditor that attributes every flag to data
   vs agent vs guardrail false-positive. That's a product I'd pay for on its own.
3. **Deterministic trajectory rules caught instrumentation mistakes**: CORR-001 (my final step
   wasn't typed `final_answer`) and EFF-001 (two verifier steps shared a tool name). Both
   fixed in minutes because the evidence string said exactly what was wrong.
4. **Setup-doctor** got me from key to `live_connected` in under ten minutes, and the
   "handshake alone doesn't count" wording prevented a false sense of done.

## What got in the way (free tier)

5. **Analysis quota.** 100 auto-analyses/day was gone in one run (a 235-deal run makes ~700
   traces + 235 trajectories); the LLM judge reported `skipped_quota` on almost everything
   and sessions showed `quality 0.0`, which reads as "scored zero" rather than "not scored".
   Suggestion: per-agent sampling (score 1 in N) and an explicit "unscored" state.
6. **Credits.** 100 credits meant I never tried Root Cause or Remediation at all — I couldn't
   risk them on experiments. A "first 3 free per project" would have got me to try them.
7. **Annotations/Evaluators locked.** I had per-deal verdicts against real ground truth and
   nowhere to write them. Workaround: trajectory steps named `check:<type>:<pass|fail>`. It
   works and shows in Agent Runs, but it's second-class — not filterable, not aggregated.
8. **Keyword guardrails cry wolf.** "Q4" matched a US driver's-licence pattern (3 traces);
   the word "bypass" in a rationale got a benign trace *blocked* (`d9aecb6e…`). A per-agent
   allowlist or a context check would fix both; a block on a false positive is costly.

## Smaller things

9. Trace *list* returns `metadata: {}` while trace *detail* has the full metadata; older trace
   details lack `agent_name` at the top level (it's inside metadata). Clients end up with
   fallbacks for both.
10. No deep-link URL scheme for a trace or trajectory id in SDK/API responses, so my UI stores
    ids but can't link to the dashboard.
11. A DNS blip during a run produced SDK warnings (`/api/traces failed: nodename nor servname
    provided`) and those traces were silently lost — no retry, no local queue.
12. `EFF-001 No Redundant Tool Calls` keys on tool *name* only; repeated verifier calls with
    different inputs are legitimate. Hash the inputs, or let the client mark a tool idempotent.
13. The documented host (`prism.blockconvey.com`) and the setup-doctor's reported host
    (`prism-api-prod.up.railway.app`) differ; both work, but a newcomer hesitates.
14. The SDK's `submit_trajectory` docstring lists `final_answer` as a step type but doesn't
    say CORR-001 depends on it; one sentence would save every first-time user the fail.
15. Trace ingestion timeout is 10 s by default; a slow period produced "read operation timed
    out" warnings mid-run. A background queue would make the SDK fire-and-forget.

## Growth trial (from Oct 15) — observations as I use it
(appended below as tested)

16. **The automatic analysis assumes a customer-facing chatbot.** Every one of my traces is
    flagged with *"Transcript contains no customer service conversation. Content is internal
    sales pipeline review data, not a customer interaction · satisfaction 0 below 40"*. An
    internal/analytical agent (pipeline review, document extraction, decisioning) gets a
    satisfaction score of 0 on everything, which then trips the satisfaction alert on every
    trace and buries real alerts. The six preset evaluators (Hallucination, Relevance,
    Toxicity, Helpfulness, Fintech Compliance, Completeness) are also phrased for chat
    responses. Suggestion: an *agent type* on the agent record — customer-facing vs internal —
    that switches the default scoring and evaluators, or at least suppresses satisfaction for
    agents with no human turn. This is the single most useful change for agents like mine.
17. **`/api/intelligence` reports `analyzed_traces: 0, coverage 0%` for a project with 3,738
    traces and 123 rows in `/api/scores`.** Either "analyzed" means something other than
    "scored" (then say which), or the counter is wrong. Either way a user reads "0%" as
    "PRISM has done nothing".
18. `/api/remediation` returns an empty list with no hint that a Root Cause run must happen
    first (and the Root Cause endpoint isn't discoverable from the API — dashboard only?).
19. **Annotations write-back works and is exactly what the "prove it" loop needs** — but the
    request fields aren't documented anywhere I could find: required `trace_id`, `verdict`;
    optional `quality_score`, `notes`, `reviewer_email`. My first attempt used `score`,
    `note`, `reviewer` and the API accepted the request while silently dropping them. A 422
    on unknown fields (or a schema in the docs) would have saved a round trip. Also:
    annotations attach to *traces*; my unit of work is a *trajectory* (one deal). I annotate
    the deal's first trace as a proxy — a trajectory-level annotation would be the natural fit.
20. **Evaluators can be created (`POST /api/evaluators` wants `name`, …) but I found no way
    to run one on existing traces from the API**; presumably they apply to new traces only.
    For a benchmark I want "run evaluator X over these 235 trajectories" and a table.
21. The trajectory list is newest-first with no `since`/`before` filter I could find; walking
    history means paging through everything.

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
10. No deep-link URL in SDK/API responses. The dashboard does have one (`/traces/{trace_id}`,
    found by clicking), so this is a documentation/response-field gap: return `url` with the
    trace and trajectory ids and clients can link straight to them. (Ledger now links to it.)
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
22. **Annotations written through the API can't be read back — through the API or the UI.** The
    Annotation queue page shows "32 pending review", all of them the satisfaction-0 flags from
    #16, and none of the 231 verdicts I wrote via `POST /api/annotations`. `POST
    /api/annotations` returns 201 with an id, but `GET /api/traces/{id}` shows no annotation,
    `GET /api/annotations?…&trace_id=` returns the pending *queue* (ignores the filter), and
    `status=all` lists only annotations on traces that had been flagged for review. I wrote 231
    verdicts and can verify none of them from the API. If they appear in the dashboard, fine —
    but an eval loop needs to read its own verdicts back (per type, over time).
23. **Ingest under sustained load stalled my pipeline.** In isolation a trace POST takes
    ~1.8 s regardless of payload size (1 KB, 8 KB, 20 KB all the same), so size isn't the
    issue. But during a 150-deal run that sends 3–4 requests/second, the SDK's 10 s timeout
    fired on most calls (`/api/traces failed: The read operation timed out`), and because the
    SDK blocks on each send, the run slowed to a crawl (0 deals finished in 25 minutes) and
    the timed-out traces were lost. I had to re-run with tracing off. Two fixes, either would
    do: a client-side queue with backoff (fire-and-forget `trace_llm`), or an async ingest
    endpoint that acknowledges immediately. Today, heavy users will turn tracing off exactly
    when it matters most.
24. **The LLM judge is on for the trial and it's good** — a fresh trajectory got
    `plan_quality / goal_alignment / tool_use_quality / reasoning_quality / safety` scores with
    one-line evidence each in ~20 s, plus an `unsupported_claims` list that caught something
    real: my `decide` step states a probability with no derivation. I'll add the decision
    model's basis to that step. Two notes: (a) the judge read the verbatim buyer quote inside
    my `check:M3_expired_promise:fail` step as a *current* claim and called it a contradiction
    ("promised PO 21 days ago… yet claims 'PO should go out next week'") — evidence quoted as
    evidence shouldn't be judged as the agent's own assertion; a convention for marking a span
    as quoted evidence (or honouring the `check:*` label) would fix it; (b) the deterministic
    overall (96) and the judged overall (84) are shown in the same `overall_score` field at
    different times, so a dashboard number can change under you without saying why.
25. **An agent's display name follows the last trace.** I sent a few latency probes with
    `agent_id="ledger"` and `agent_name="ledger-probe"`; the dashboard's Agent Fleet now lists
    my whole agent as "ledger-probe" and Recent Activity shows "ledger-v1 · latency probe".
    The SDK docstring says the id is the identity and the name a label, which is right — but
    the label should be set once (or per id), not overwritten by whatever the newest trace says.
26. **A trace page says "No step spans recorded. Configure your SDK to capture tool calls and
    handoffs" even when the same session has trajectories with 6–9 steps each.** Traces and
    trajectories (Agent Runs) live in separate worlds in the UI: the trace page doesn't link to
    the run it belongs to, and the run doesn't list its traces. Joining them on `session_id`
    (or letting the client pass `trajectory_id` on a trace) would turn two lists into one story.
27. Dashboard deep links exist (`/traces/{id}`) — found by clicking; worth returning in the API
    so clients can link (see #10). Also useful: `/traces?agent=&status=flagged&range=30d` as a
    shareable URL — today the filters reset on navigation.
28. **"Errors: 393" on the Agent Runs page counts my runs with `final_status=error`, which I
    set deliberately when a deal has an open finding.** That's the only status besides success,
    so a run that *found something* and a run that *crashed* look the same in the KPI tile. A
    third status — `flagged` / `attention` — would keep "errors" meaning errors.
29. The Evaluation tab is excellent (judge model shown — claude-haiku-4-5 — scores per
    dimension with rule counts, 723 ms). Two asks: let me filter runs by evaluation outcome
    (e.g. correctness < 90) and export the per-run scorecards as CSV; today the only
    aggregate is the KPI strip.

### Event day (Oct 17, Growth trial, Money Talks 2 resource pack in hand)

30. **Root Cause does nothing until someone presses "Analyze now".** A project with 3,983
    traces and ~900 trajectories had zero clusters and zero per-trace analyses on the morning of
    the event; the API confirmed it (`/api/intelligence` → `analyzed_traces: 0`,
    `/api/intelligence/clusters` → `total: 0`). One `POST /api/intelligence/clusters/analyze`
    (5 credits) produced six clusters in ~50 s from trajectories alone. The dashboard copy then
    says "Only 0 of 3,983 traces (0%) have per-trace analysis, which clusters are built from" —
    but the clusters it just built came from trajectory rules, not per-trace analysis, so the
    sentence contradicts the screen. Suggest: schedule a clustering run automatically once a
    project crosses N trajectories (free when nothing changes, as you already do), and say
    which of the two sources each cluster came from.
31. **The backfill endpoint wants the internal row `id`, not the SDK `trace_id`.**
    `POST /api/backfill/trace-analyses/quote` with the 52 `trace_id`s I minted returned
    `candidates: 0` (no error, no hint); the same call with the `id` field from
    `/api/sessions/{id}` returned `candidates: 52`. Every other endpoint I used accepts the
    `trace_id`. Accept both, or reject unknown ids loudly.
32. **Trajectory rules have undocumented status semantics, and they cluster.** I sent
    `final_status=error` to mean "this deal has an open finding" (see #28) and marked the
    verifier's dropped-claim step `error` because a claim failed the check. Root Cause's
    first run turned that into a *rising, high-severity* cluster of 470 "failures in
    ledger-v3" with cause `tool` (`failed_tool_call, unsupported_answer`, judge 100%
    self-consistent). The judge was consistent and wrong because the inputs were mislabelled;
    nothing in the SDK or docs says what CORR-001 / ROB-001 read. A one-line table —
    rule → fields it reads → what counts as failure — would have saved the morning. (Fix on my
    side: FINDINGS.md #18.)
33. **CORR-002 "Reasoning Presence" and CORR-004 "Logical Step Sequence" fail 100% of a
    deterministic pipeline's runs** ("tool call as first step", "repeated tool_call more than
    5 times consecutively", "reasoning steps 0/13"). My auditor flagged it automatically from
    `/api/trajectories/{id}/evaluation`. A rules-then-model pipeline legitimately starts with
    a tool and runs many tools back to back; these rules encode a ReAct chatbot. Either let a
    project pick a rule profile ("pipeline agent" vs "conversational agent") or weight these
    rules down when the run has `check:*` steps and a `final_answer`. I'm adding reasoning
    steps that describe the plan and the assessment, which is honest, but I'm doing it for the
    rule, not for the user.
34. **Alert metrics are a closed list that only the 400 error reveals.** The resource pack
    says "set an alert on failed tool call, cost, latency"; the API's `known_metrics` are
    `compliance_score, error_rate, evaluation_failed, guardrail_blocks, latency,
    satisfaction_score, trace_failures_per_hour, traces_per_hour` — no cost, no failed tool
    call, and the list is nowhere in the docs. Rules scoped to `agent_id` work and the
    create/list/fired endpoints are clean; please publish the metric list and add
    `cost_usd` and `step_errors` (an `error` step inside a trajectory).
35. **Sessions → Steps is the best page for a pipeline agent, and it shows one run per
    session.** A session of 230 traces (one rep, 47 deals, ~5 calls each) has `agent_run_id`
    = the last trajectory. The Steps tab is exactly what the Money Operations proof asks for,
    but a reviewer can't pick which deal's run to look at from the session. A run picker (or
    a `session_id` filter on Agent Runs that lists all of them) would close the loop with #26.
36. **Judge framing on the session page.** The header reads "Session · Resolved · 1.1s" and
    the card is "Compliance Score Trend — Risk & Compliance"; "Industry: —". For an internal
    pipeline-review agent none of those words apply; the trace-level judge likewise opens with
    "Transcript contains no customer service conversation" (#16). The scoring itself is fine;
    the vocabulary around it tells a non-chatbot user they are in the wrong product.
37. **Pricing clarity is good**: `/api/backfill/trace-analyses/quote` and the readiness
    endpoint say the exact credits before anything runs, and the Root Cause page states
    "a run that changes no cluster is free". That is how metered analysis should behave.
38. **Alert rules fire once, then go quiet.** The latency rule fired at 13:29 on a 25.9 s call;
    the next three hours produced dozens of traces at 60–200 s (streamed naive-agent batches)
    and no further firing, and `/api/alerts/fired` still lists one. If there is a cooldown or a
    one-per-pattern rule, say so on the rule; otherwise a reviewer concludes the problem
    stopped.
39. **Per-trace judge coverage ran out silently.** Every trace from the day's 1,500+ calls has
    `evaluation: null`; the morning's traces were scored. Nothing in the API or the dashboard
    said a daily cap was reached — the Intelligence page just offers "Analyze for 4,600
    credits". A `quota` field on `/api/intelligence` (scored today / cap) would make the
    cliff visible.
40. **Clustering lags evaluation.** Five trajectories evaluated at 14:00 (rules failing) were
    not in any cluster after a run started at 14:25; the run reported "no new failures" for
    them. Either the window excludes the newest runs or assignment is asynchronous; a
    `pending_assignment` count on the run summary would tell.
41. **The API key cannot see the repo the dashboard connected.** After installing the GitHub
    App and selecting `happyc0der/ledger` (Connectors → Code repository shows *Connected · base:
    master · auth: GitHub App · LLM consent recorded*), `POST /api/intelligence/clusters/reverify-main`
    with the project API key still answers "No connected GitHub repo with credentials for this
    project", and `GET /api/repos` wants a user bearer token. Localisation did run on four
    singleton clusters (candidate prompt files + a suspect commit), so the connection works
    for the engine; it is the API surface that disagrees. Either let the project key read the
    repo record, or say in the error that this endpoint needs a user session.

Hi [name] — Keshav here (Ledger, Money Operations track at Money Talks 2). You asked for feedback on PRISM; here is the short version from two weeks of wiring a pipeline agent into it, about 6,000 traces and 1,500 runs. The full log is 43 items with trace ids: github.com/happyc0der/ledger/blob/master/docs/PRISM_FEEDBACK.md

What worked, so you keep it: setup-doctor got me to live_connected in ten minutes; the read API is solid enough to build an auditor on; the deterministic trajectory rules caught three real instrumentation mistakes of mine; the LLM judge's Evaluation tab is excellent; and every metered action quotes its exact credit cost before it runs. That last one is rare and right.

What I would fix first:

1. Root Cause is invisible until someone presses Analyze. A project with 4,000 traces had zero clusters on event morning. Schedule a run once a project crosses N trajectories (it is free when nothing changes, as you already do), and say on each cluster whether it came from trajectory rules or per-trace analysis — today the page says clusters are "built from" per-trace analysis right above clusters that were not.

2. Rule semantics are undocumented, and they cluster. I sent final_status=error to mean "this deal needs attention" and got a rising, high-severity cluster of 470 "failures". One table — rule → fields it reads → what counts as a failure — would have saved me a morning. Related: CORR-002 (reasoning presence) and CORR-004 (no more than five tool calls in a row) fail every run of a rules-then-model pipeline; a "pipeline agent" rule profile, or down-weighting them when a run has check steps and a final answer, would fix that.

3. UI: traces and runs live in separate worlds. A trace page says "No step spans recorded" while the same session has 12-step runs; the run does not list its traces; Sessions → Steps shows only the last run of a session that holds 47 of them. Join them on session_id, add a run picker, and return the dashboard deep link in the API. Also: the "Errors" KPI tile counts final_status=error, so a run that found something and a run that crashed look the same; filters reset on navigation; the session header says "Resolved · 1.1s · Risk & Compliance · Industry —" to a non-chatbot user; and the RCA summary tells a hosted-product user to "configure ANTHROPIC_API_KEY".

4. Alerts: the metric list only appears in the 400 error, there is no cost or failed-tool-call metric although the event brief suggests both, a rule fires once then goes quiet with no visible cooldown, and a cached replay re-fired the latency rule. Honour a cached flag in metadata.

5. Quotas and coverage fail silently. 1,500 traces in a day got evaluation: null with nothing in the API or UI saying the daily analysis cap was reached. A "scored today / cap" field would do it.

6. API consistency: the backfill endpoint wants the internal row id, not the trace_id every other endpoint accepts (it returns candidates: 0, no error); trace list returns empty metadata while detail has it; no since/before filter on trajectories; the project API key cannot see the repo the dashboard connected, so reverify-main answers "no connected repo"; and localisation skips trajectory-only clusters, which are the ones that matter for an agent that does not chat.

7. Keyword guardrails cry wolf: "Q4" matches a US driver's-licence pattern on every trace that mentions a quarter.

Happy to walk through any of these with trace ids, and to be a design partner for the pipeline-agent profile — that is the shape most agents moving money will have.

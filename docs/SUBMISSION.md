# Submission — Ledger (Money Talks 2 · Money Operations)

**One line.** Ledger is the revenue forecast with receipts: it reads what the *buyer* actually
said on every deal, finds where the record and the CRM disagree, and produces a commit number
where every dollar — and every excluded dollar — has a quote behind it.

**What it does.** Ingests a HubSpot/Salesforce export → resolves who said what → extracts a
claim ledger of buyer-stated facts with verbatim quotes → compares it in code against CRM
fields (18 checks: 8 field rules + 10 semantic contradictions, including cross-deal) → judges
each deal → forecasts commit/best case from deals with no open issue → drafts CRM corrections
a human approves → writes Monday digests → audits itself through PRISM.

**Built with Nicrron.** Every model call on event day ran through the Nicrron API
(`anthropic/claude-sonnet-5-5`, `LLM_PROVIDER=nicrron`), traced to PRISM under tagged sessions.
Gateway lessons (60 req/min, 4,096-token cap with empty content on truncation, 30 s upstream
timeout → streaming) are in docs/NICRRON_NOTES.md.

**Proof (235 deals, outcomes hidden; event-day run on Claude Sonnet 5.5 via Nicrron).** CRM
rules: 0% of semantic problems. The same model asked to "find the issues": 72% recall, 10 of
86 clean deals falsely flagged, 6 fabricated numbers. Ledger: 94% recall, 99% precision,
**0 of 86** clean deals flagged, **0** fabrications; revenue in the top-20 64% → 71%;
objection accuracy 68% → 95%. September run on Gemini Flash-Lite: naive 32% / 17% false
alarms / 97 fabrications → Ledger 92% / 100% / 0, top-20 60% → 77%. On a free 12B model on a laptop GPU (Oct 17, 45 min, $0): 80% / 95% / 0 of 86, top-20 82%. On 150 independent SaaS conversations with real outcomes: verification
transfers (0 fabrications, 85% of closable revenue), the fallback judgement does not — the
auditor caught it.

**The three Money Operations proofs.** (1) *Sessions → Steps*: every deal is a 10–13-step
run — crm · rules · claim ledger · verifier · consistency checks · decision · quote verifier ·
final answer — `prism.blockconvey.com/sessions/v3-Niesha_Huffines-sonnet`. (2) *Alert*: rules scoped to
the ledger agent — "model call stalled > 20 s" and "prompt blocked by a guardrail" — the first
fired on a real run on Oct 17 09:29 (25.9 s call). (3) *Root Cause*: the failure is the naive agent — its runs on
the same 235 deals cluster as failures with a cause (unsupported answers: fabricated quotes,
amounts and day gaps, recorded as `check:*:mismatch` steps; 8 traces analysed, then Analyze
now); the fix is Ledger — same inputs, same model, 17/17 trajectory rules pass; PRISM's own Agent
Intelligence narrative on the naive agent reads "Agent fabricates deal data on pipeline
reviews … add guardrails to prevent deal fabrication" — which is the v3 design.

**The PRISM loop.** Build → Observe (every call a trace, every deal a run with `check:*`
steps) → Discover (PRISM's PII guardrail flagged phone numbers that existed nowhere in our
data: a paraphrase step had invented them; on event day Root Cause clustered 470 of our own
runs as failures because we had overloaded `final_status`) → Improve (23 fixes logged in
FINDINGS.md with trace ids) → Prove (same deals re-run; flags gone; rules 17/17; numbers
above). A third agent, the auditor, reads PRISM back and attributes every failure to data /
agent / guardrail / instrumentation; it caught a duplicated run file and a model's false
"paused" label on the day. 37 items of product feedback for the PRISM team are in
docs/PRISM_FEEDBACK.md.

**What is real.** Deals, values, dates, outcomes: public Maven CRM dataset. Notes and anomalies:
synthetic, planted with labels, disclosed. Second dataset: public SaaS conversations with real
outcome labels. Every adjustment made after a measurement is listed in FINDINGS.md.

**Links.** Repo: https://github.com/happyc0der/ledger · System design: docs/SYSTEM_DESIGN.md ·
Demo script: DEMO.md · Video: docs/video/ledger_demo_backup.mp4 · Scored tables: docs/reports/ · Findings log: FINDINGS.md · Live run: `scripts/live.py`
on `data/templates/` (edit the CSV, ~12 s).

**Not yet.** Jev (TypeSafe) as the judgement layer — waitlisted; `decide.py` switches on the key.

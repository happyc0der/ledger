# Submission — Ledger (Money Talks 2 · Money Operations)

**One line.** Ledger is the revenue forecast with receipts: it reads what the *buyer* actually
said on every deal, finds where the record and the CRM disagree, and produces a commit number
where every dollar — and every excluded dollar — has a quote behind it.

**What it does.** Ingests a HubSpot/Salesforce export → resolves who said what → extracts a
claim ledger of buyer-stated facts with verbatim quotes → compares it in code against CRM
fields (18 checks: 8 field rules + 10 semantic contradictions, including cross-deal) → judges
each deal → forecasts commit/best case from deals with no open issue → drafts CRM corrections
a human approves → writes Monday digests → audits itself through PRISM.

**Proof (235 deals, outcomes hidden).** CRM rules: 0% of semantic problems. The same model
asked to "find the issues": 32% recall, 17% false alarms. Ledger: 92% recall, 100%
precision, 0 of 86 clean deals flagged; revenue in the top-20 60% → 77%; fabrications 97 → 0.
On a free local model: 82% / 91% / 1 of 86. On 150 independent SaaS conversations with real
outcomes: verification transfers (0 fabrications, 85% of closable revenue), the fallback
judgement does not — the auditor caught it.

**The PRISM loop.** Build → Observe (every call a trace, every deal a run with `check:*`
steps) → Discover (PRISM's PII guardrail flagged phone numbers that existed nowhere in our
data: a paraphrase step had invented them) → Improve (two-way fact check; 16 fixes logged in
FINDINGS.md with trace ids) → Prove (same deals re-run; flags gone; numbers above). A third
agent, the auditor, now reads PRISM back and attributes every failure to data / agent /
guardrail / instrumentation. 29 items of product feedback for the PRISM team are in
docs/PRISM_FEEDBACK.md.

**What is real.** Deals, values, dates, outcomes: public Maven CRM dataset. Notes and anomalies:
synthetic, planted with labels, disclosed. Second dataset: public SaaS conversations with real
outcome labels. Every adjustment made after a measurement is listed in FINDINGS.md.

**Links.** Repo: https://github.com/happyc0der/ledger · System design: docs/SYSTEM_DESIGN.md ·
Demo script: DEMO.md · Video: docs/video/ledger_demo_backup.mp4 · Live run: `scripts/live.py`
on `data/templates/` (edit the CSV, ~12 s).

**Not yet.** Jev (TypeSafe) as the judgement layer — waitlisted; `decide.py` switches on the key.

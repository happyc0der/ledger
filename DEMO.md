# Demo script — 3 minutes

Setup before walking up: UI on :8787 (benchmark data, v3 selected, Proof tab pre-loaded once),
a second UI on :8788 pointed at `data/live`, PRISM dashboard open on Traces filtered to
`ledger-v1`, terminal with the live command pasted, backup video one tab away.

**0:00 — The problem (20s).** "Every Monday a sales manager reviews ~200 deals in 30 minutes
using stages the reps set. CRM alerts see fields. Reps are optimistic. We built a revenue
agent whose job is to notice when a deal doesn't make sense — and to show a receipt for
every claim."

**0:20 — What your CRM already tells you (20s).** Proof tab, second table. *CRM rules*:
99% of the field problems — past close dates, blank amounts, dormant deals. Point at the
semantic row: **0%**. "Stage contradicting the buyer. A champion who left. A promise that
expired. A deal the buyer already lost. None of that is in a field."

**0:40 — The deal (45s).** Pipeline tab, click **Dontechi · GTXPro** (`P9VFKNR0`,
Darcel Schlecht, Negotiation, $4,821). CRM says Negotiation, close Nov 13. Ledger says
p=25%, *multithread to the economic buyer*, and four receipts: buyer "suspend all new vendor
onboarding" (Sep 27) vs stage Negotiation · close date Nov 13 vs a paused buyer · rep on
Oct 18 "engagement remains high" — happy ears · auto-reply: Kwame left. "The model reads;
code compares; nothing without a quote is shown." Open *Checks run*: 18 checks, which
passed and why.

**1:25 — The cross-deal one (15s).** Click the sibling **Dontechi** deal (`OEBJXZN6`): rated
85%, "PO next week" — and Ledger: *primary contact left Dontechi, per the auto-reply on
P9VFKNR0*. "A rules engine can't do that. A rep in a hurry won't."

**1:40 — Prove it (35s).** Proof tab, first table: 235 deals, 18 planted anomaly types,
outcomes hidden. Rules 0% semantic. The *same model* just asked to find issues: 32% recall,
17% of clean deals falsely flagged. Ledger: 92% recall, 99% precision, **0 clean deals
flagged**. "That last number is the one a RevOps team feels — an agent that cries wolf gets
muted in a week." Then the outcome table: revenue in the top-20 60% → 77%, fabrications
97 → 0, same real outcomes.

**2:15 — How PRISM found our own bug (20s).** PRISM Traces, `ledger-v1`, PII flags: phone
numbers. None exist in the data. The model we used to paraphrase notes had *invented* them.
The auditor traced the flags to the data, not the agent; fixed; flags gone. `FINDINGS.md`,
13 rows, each with its PRISM evidence and re-proof.

**2:35 — Live (20s).** Terminal: `scripts/live.py` on the 8-deal HubSpot template a judge
can edit. ~12 seconds. :8788 — Fabrikam: contact left + 31-day-old "PO next week" +
the sibling deal still listing her; Northwind: leaning to Kestrel while the rep says "still
in it". Toggle a proposal: *replace primary contact → Tom Brandt* — approve — export.

**2:55 — Close (5s).** "If a pipeline review can't show its receipts, it's a guess with a
nice UI. Ledger shows them — every Monday."

## If asked
- *Is the data real?* Deals, values, dates, outcomes: yes (public Maven CRM dataset). Notes
  and anomalies: synthetic, planted with labels, disclosed in the README. The live CSV is
  hand-written and editable — change a sentence and re-run.
- *Why not just a better prompt?* We measured it: the same model asked to "find the issues"
  gets 32% recall and flags 17% of clean deals (KC-Bench's result, reproduced). Ledger's
  model only reads into a schema; code compares.
- *Did you tune to the labels?* No prompt or model change after scoring. Comparison bugs
  were fixed and label gaps closed — every one listed in the README and FINDINGS.md.
- *Real exports?* HubSpot/Salesforce presets; attribution from email direction and
  addresses; ingest refuses an export where nothing is attributable to a buyer. Custom
  stages kept. Thresholds learned from closed deals.
- *Cost?* ~$0.35 for a full 235-deal run on Gemini Flash-Lite; a weekly re-run costs cents
  because unchanged records reuse their ledger. Runs on a local model for free.
- *Write-back?* Drafts only; a human approves; export in the CRM's own columns.
- *Calibration?* Fallback decision model is uncalibrated and the UI says so; Jev slots in.

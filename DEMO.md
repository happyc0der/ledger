# Demo script — 3 minutes

**0:00 — The problem (20s).** "Every Monday a sales manager reviews ~200 deals in 30
minutes using stages the reps set. Reps are optimistic, and CRM alerts only see fields. We
built a revenue agent whose job is to notice when a deal doesn't make sense — and to show
its receipts for every claim."

**0:20 — What your CRM already tells you (20s).** Proof tab, top table: *CRM rules*. Past
close dates, blank amounts, dormant deals: 99% of those. "And zero of these" — point at the
semantic row: stage contradicting the buyer, a champion who left, a promise that expired, a
deal the buyer already lost, a missing economic buyer.

**0:40 — What Ledger does (40s).** Click a deal with three issues. Drawer: CRM says
Negotiation, $5,482, close Nov 12, contact Priya. Ledger: "Priya left (auto-reply, Oct 2)"
— quote. "Buyer promised a PO on Sep 29; nothing since" — quote. "No economic buyer on a
late-stage deal." → "multithread to Daniel Kowalski, or disqualify." "The model reads;
code compares; nothing without a quote is shown."

**1:20 — The cross-deal one (15s).** Click the sibling deal at the same account: "primary
contact left, per the auto-reply on the other deal." "A rules engine can't do that. A rep
in a hurry won't."

**1:35 — Prove it (40s).** Proof tab: 235 deals, 18 planted anomaly types, outcomes hidden.
Rules: 0% semantic. Ledger: 93% recall, 99% precision, **one clean deal falsely flagged out
of 86**. "That last number is the one a RevOps team cares about — an agent that cries wolf
gets muted in a week." Then the older table: revenue in the top-20 53% → 71%, fabrications 68
→ 0, Brier — same 228 deals, real outcomes.

**2:15 — How PRISM found our own bug (20s).** PRISM's PII guardrail flagged v1 for phone
numbers. None exist in the data. The model we used to paraphrase the notes had invented
them. Our auditor agent traced the flags to the data, not the model. "Observability found a
failure in *our* pipeline before a judge did." Show `reports/audit.md`.

**2:35 — Live (15s).** Toggle v1: watch the receipts go red and the issues disappear.
Toggle v3 back. Tick "reveal outcomes."

**2:50 — Close (10s).** "If a pipeline review can't show its receipts, it's a guess with a
nice UI. Ledger shows them — and tells you what doesn't add up."

## If asked
- *Is the data real?* Deals, values, dates, outcomes: yes (public Maven CRM dataset). Notes
  and anomalies: synthetic, planted with labels, disclosed in the README.
- *Why not just a better prompt?* KC-Bench: agents asked to "notice conflicts" miss explicit
  ones. Ours doesn't notice — it reads into a schema and code compares. The fixes are
  architectural: what the model is allowed to decide.
- *Did you tune to the labels?* No prompt or model change after scoring. Two comparison bugs
  fixed; three true-but-unlabelled situations added to the labels, all disclosed.
- *Cost?* Under $1 for a full run on Gemini Flash-Lite; runs on a local model for free.
- *Production?* CSV in today; the loader is one file. Salesforce/HubSpot adapter is the
  obvious next step; the findings API already exists (`/api/deals`, `/api/deal/{id}`).

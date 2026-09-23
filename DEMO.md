# Demo script — 3 minutes

**0:00 — The problem (20s).** "Every Monday a sales manager reviews ~200 deals in 30
minutes, using stages the reps set. Reps are optimistic. We asked an AI agent to do the
review — and then checked every line it wrote against what actually happened."

**0:20 — v1, the agent everyone builds first (40s).** UI, toggle `v1`. It reads well.
Click a top-ranked deal: Negotiation, 90%. Reveal outcome: lost — the buyer had written
"budget frozen until next fiscal year" three weeks earlier. Switch to PRISM: the v1 trace
for that rep. Point at the pipeline total: $109K short, because one product is spelled two
ways. Point at a day-gap the model computed: it counted the rep's voicemails as buyer
contact. "It fabricated 65 of those. You cannot tell which from the output."

**0:50 — The failure we didn't plant (10s).** PRISM's PII guardrail flagged v1 for phone
numbers and emails. None exist in our data — the model we used to paraphrase the notes had
invented them. Observability found a bug in *our* pipeline before a judge did.

**1:00 — The fix (30s).** One deal per context. Numbers from code. Decisions as calibrated
probabilities from a decision model, not prose. A quote must exist verbatim in the record
or it's dropped. Every check is a step in PRISM. Show the v2 trajectory for the same deal:
`check:quote:match`, `check:amount:match`.

**1:30 — Same 228 deals, scored against reality (60s).** Proof tab. Revenue in the top-20:
53% → 71% — "that's $21K of rep time pointed at the right deals in one team-week."
Fabrications 68 → 0. Pipeline error 18% → 0. Reliability: read the two top bins off the Proof tab. "Overconfidence isn't a calibration footnote — it's why v1's top 20
was just the 20 biggest deals."

**2:30 — Live (20s).** Toggle `v2`, click a deal, read the buyer's own sentence and the
one action. Tick "reveal outcomes."

**2:50 — Close (10s).** "If a pipeline review can't show its receipts, it's a guess with a
nice UI. Ledger shows them — and PRISM is where we found out we needed to."

## If asked
- *Is the data real?* Deals, values, dates, outcomes: yes (public Maven CRM dataset). Notes:
  synthetic, conditioned on the real outcome, disclosed in the README.
- *Why not just a better prompt?* We tried; a stronger model made v1 read better and still
  fabricate. The fixes are architectural: what the model is *allowed* to decide.
- *Cost?* about $0.30 for the full comparison. Default runs on a local model for free.

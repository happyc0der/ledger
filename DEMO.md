# Demo script — 3 minutes

**Setup:** `./scripts/demo_up.sh` — starts the three UIs, checks PRISM and the Nicrron balance,
prints the bookmarks below. **:8787 is the event run: Claude Sonnet 5.5 through Nicrron, as the
organisers require** (:8789 keeps the September Gemini run for the "same pipeline, other model" question).
Stage URLs: proof `localhost:8787/?view=proof` · the deal `?deal=P9VFKNR0` · sibling
`?deal=OEBJXZN6` · the invented number `?version=v1&deal=CMCVD0N8` · the invented day gap
`?version=v1&deal=GZ5M7MIQ` · digest `?digest=1` · live export `localhost:8788/?deal=2003` ·
PRISM proof 1 `prism.blockconvey.com/sessions/v3-Niesha_Huffines` (Steps tab) · proof 2 `/alerts` ·
proof 3 `/root-cause` and `/intelligence`. Backup video: `docs/video/ledger_demo_backup.mp4`.

Setup before walking up: UI on :8787 (event run, v3 selected, Proof tab pre-loaded once), the
live UI on :8788, PRISM dashboard logged in with the three proof pages in tabs, terminal with
the live command pasted (`LLM_PROVIDER=nicrron`), backup video one tab away.

**0:00 — The problem (20s).** "Every month a finance team signs a revenue forecast built from
a CRM that reps fill in optimistically. The CRM's own alerts only see fields. We built Ledger:
it reads what the *buyer* actually said on every deal, finds where the record and the CRM
disagree, and produces a commit number where every dollar has a receipt."

**0:20 — What your CRM already tells you (20s).** Proof tab, second table. *CRM rules*:
99% of the field problems — past close dates, blank amounts, dormant deals. Point at the
semantic row: **0%**. "Stage contradicting the buyer. A champion who left. A promise that
expired. A deal the buyer already lost. None of that is in a field."

**0:40 — The deal (45s).** Pipeline tab, click **Dontechi · GTXPro** (`P9VFKNR0`,
Darcel Schlecht, Negotiation, $4,821). CRM says Negotiation, close Nov 13. Ledger says
p=10%, *multithread to the economic buyer*, and four receipts: buyer "suspend all new vendor
onboarding" (Sep 27) vs stage Negotiation · close date Nov 13 vs a paused buyer · rep on
Oct 18 "engagement remains high" — happy ears · auto-reply: Kwame left. "The model reads;
code compares; nothing without a quote is shown." Open *Checks run*: 18 checks, which
passed and why. Every model call you are looking at went through Nicrron this morning.

**1:25 — The cross-deal one (15s).** Click the sibling **Dontechi** deal (`OEBJXZN6`): the
naive agent rates it 75% on "Nadia Osei approved it" — and Ledger: *primary contact left
Dontechi, per the auto-reply on P9VFKNR0*. "A rules engine can't do that. A rep in a hurry won't."

**1:40 — Prove it (35s).** Toggle to v1 on **Warephase · GTXPro** (`CMCVD0N8`): the buyer
wrote "2 units at list, so $14,463 total"; the naive agent copies $14,463 into the forecast;
Ledger: *2 × $4,821 is $9,642* — M10, the buyer's own arithmetic, caught before a PO. Then the
forecast strip: "commit $274,814, best case $472,060 — and *why* each excluded dollar is
excluded is one click away." Then the Proof tab: 235 deals, 18 planted anomaly types,
outcomes hidden. Rules 0% semantic. The *same model* (Claude Sonnet 5.5) just asked to find
issues: 72% recall, 10 of 86 clean deals falsely flagged, 6 invented numbers. Ledger: 94%
recall, 99% precision, **0 clean deals flagged, 0 invented numbers**. "A better model helped
the naive agent a lot — in September on Gemini it was 32% and 17% — and it still invents.
The zero is structural." Outcomes: revenue in the top-20 64% → 71%, objection accuracy 68% → 95%.

**2:15 — PRISM: the failure, the fix, the alert (25s).** Root Cause: the `ledger-v1` cluster —
five of this morning's naive runs, cause *prompt*, "unsupported answers, errors never
recovered" — and the `ledger-v3` cluster whose last failure is yesterday: same deals, no
failures since the fix. Agent Intelligence, PRISM's own words on the naive agent: *"Agent
fabricates deal data on pipeline reviews… add guardrails to prevent deal fabrication."* Alerts:
*model call stalled > 20 s* fired at 09:29 on a real run. Sessions → Steps: every deal is a
10-step run, every check visible. "PRISM also clustered 470 of *our* runs as failures this
morning — we had sent open findings as errors. Finding 18. Fixed, re-proved: 17 of 17 rules."
`FINDINGS.md`, 23 rows, each with its PRISM evidence and re-proof.

**2:35 — Live (20s).** Terminal: `scripts/live.py` on the 8-deal HubSpot template a judge
can edit. ~12 seconds. :8788 — Fabrikam: contact left + 31-day-old "PO next week" +
the sibling deal still listing her; Northwind: leaning to Kestrel while the rep says "still
in it". Toggle a proposal: *replace primary contact → Tom Brandt* — approve — export.

**2:55 — Close (5s).** "A forecast without receipts is a guess with a nice spreadsheet.
Ledger gives finance the receipts — every Monday, and before the CFO signs."

## If asked
- *Is the data real?* Deals, values, dates, outcomes: yes (public Maven CRM dataset). Notes
  and anomalies: synthetic, planted with labels, disclosed in the README. The live CSV is
  hand-written and editable — change a sentence and re-run.
- *Why not just a better prompt / a better model?* We measured both: the same model asked to
  "find the issues" gets 32% recall and flags 17% of clean deals on Gemini, 72% and 12% on
  Sonnet 5.5 — better, still wrong. Ledger's model only reads into a schema; code compares.
- *Did you tune to the labels?* No prompt or model change after scoring. Comparison bugs
  were fixed and label gaps closed — every one listed in the README and FINDINGS.md.
- *Real exports?* HubSpot/Salesforce presets; attribution from email direction and
  addresses; ingest refuses an export where nothing is attributable to a buyer. Custom
  stages kept. Thresholds learned from closed deals.
- *Cost?* ~$6 for a full 235-deal run on Claude Sonnet 5.5 through Nicrron (gateway meter),
  ~$0.35 on Gemini Flash-Lite, free on a local model; a weekly re-run costs cents because
  unchanged records reuse their ledger.
- *Why is the top-20 number lower on Sonnet than on Gemini (71% vs 77%)?* Same deals, same
  code, different reader; both beat the naive agent on the same model (64% and 60%). The
  judgement layer is the fallback model either way — Jev is the intended judge.
- *Write-back?* Drafts only; a human approves; export in the CRM's own columns.
- *Calibration?* Fallback decision model is uncalibrated and the UI says so; Jev slots in.

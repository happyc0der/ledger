# Demo script — 3 minutes, in plain words

Every beat has three lines: **CLICK** (what you do), **SAY** (what you say, in your own words),
**SEE** (what the audience is looking at, so you know it worked).

## Before you walk up (2 minutes)

1. Run `./scripts/demo_up.sh`. Seven lines must say OK or 200, and the Nicrron line must show a balance.
2. Hard-reload `http://localhost:8787` once (Cmd+Shift+R). Click **Proof** once so it is cached. Click **Pipeline** again.
3. Open these tabs in this order and leave them:
   - A `localhost:8787/?deal=P9VFKNR0`
   - B `localhost:8787/?deal=OEBJXZN6`
   - C `localhost:8787/?version=v1&deal=CMCVD0N8`
   - D `localhost:8787/?view=proof`
   - E `prism.blockconvey.com/root-cause`
   - F `prism.blockconvey.com/intelligence`
   - G `prism.blockconvey.com/alerts`
   - H `prism.blockconvey.com/sessions/v3-Niesha_Huffines-sonnet` → click **Steps**
   - I `localhost:8788/?deal=2003`
4. Terminal open in `~/Projects/ledger` with this pasted, not yet run:
   `LLM_PROVIDER=nicrron .venv/bin/python scripts/live.py --preset hubspot --deals data/templates/hubspot_deals.csv --activities data/templates/hubspot_engagements.csv --contacts data/templates/hubspot_contacts.csv --products data/company/products.csv --as-of 2026-10-19`
5. Backup video `docs/video/ledger_demo_backup.mp4` open in a player, paused. If anything breaks, play it and talk over it.

---

## 0:00 — The problem (20 s)

**CLICK** nothing yet. Tab A is on screen.

**SAY** "Every month a finance team signs a revenue forecast. The forecast comes from a CRM
that sales reps fill in optimistically. The CRM's alerts only look at fields — dates, amounts.
They can't read what the customer actually wrote. Ledger reads every email and call note,
compares what the *buyer* said with what the CRM claims, and gives you a forecast where
every dollar has a receipt. Every model call today ran through Nicrron."

**SEE** the pipeline list with the Dontechi deal open on the right.

## 0:20 — One deal (45 s)

**CLICK** stay on tab A. Point at the right-hand panel.

**SAY** "This is Dontechi. The CRM says Negotiation, closing November 13th, $4,821. Ledger says
10% and tells you why, with four receipts. The buyer wrote 'suspend all new vendor onboarding'
— so the stage is wrong. The close date is in four weeks — but the buyer paused. The rep wrote
'engagement remains high' *after* that — happy ears. And an auto-reply says the champion left
the company. Every one of those is the buyer's own sentence. If there is no sentence, Ledger
shows nothing."

**CLICK** open **Checks run**.

**SAY** "Eighteen checks ran on this deal. You can see which passed and why. That is what a
RevOps team needs to trust it."

**SEE** the four findings with quotes; then the list of checks with pass / fail / skipped.

## 1:05 — The deal a rules engine can't see (15 s)

**CLICK** tab B.

**SAY** "Same customer, second deal. The naive agent rates this one 75% because 'Nadia approved
it'. Ledger says: the contact on this deal left the company — we know from the auto-reply on the
*other* deal. A rules engine can't connect two deals. A rep in a hurry won't."

**SEE** one finding: primary contact left, per the auto-reply on P9VFKNR0.

## 1:20 — The invented number (20 s)

**CLICK** tab C. The left list shows the naive agent (v1).

**SAY** "Here is what happens without the receipts. The buyer wrote '2 units at list, so
$14,463 total'. The naive agent copies $14,463 into the forecast. Ledger checks the arithmetic:
2 times $4,821 is $9,642. The buyer's own mistake, caught before a purchase order."

**SEE** the red ✗ amount receipt on Warephase; the v1 panel shows $14,463.

## 1:40 — Prove it (35 s)

**CLICK** tab D.

**SAY** "Same 235 deals. Real deals, real outcomes, hidden from the agent. Top table: against
what actually happened. Bottom table: against eighteen kinds of problems we planted. Rules
find none of the semantic ones — zero. The *same model* just asked to 'find the issues' finds
72% and raises false alarms on 10 clean deals out of 86, and invents 6 numbers. Ledger: 94%,
zero false alarms, zero invented numbers. In September on a cheaper model the naive agent was
at 32% with 17% false alarms. A better model helped it. It still invents. The zero is
structural — the model only reads, code does the comparing. And the commit number at the top is
the one you can defend line by line: every dollar in or out has a receipt."

**SEE** the two tables; the 0 / 86 and the 0 fabrications in green.

## 2:15 — PRISM: the failure, the fix, the alert (30 s)

**CLICK** tab E.

**SAY** "This morning PRISM showed us our agent was misreporting itself. It clustered 470 of
our runs as failures, because we sent 'error' to mean 'this deal needs attention'. We fixed how
we instrument, re-ran the same 235 deals, and they pass 17 of 17 rules. Our auditor, reading
PRISM back, caught two more rules the same way. Finding 18 in our log, 26 findings in all."

**CLICK** tab F.

**SAY** "And this is PRISM's own verdict on the naive agent, nobody prompted it: 'fabricates
deal data on pipeline reviews — add guardrails to prevent deal fabrication.' That is the
Ledger design, in their words."

**CLICK** tab G, then tab H.

**SAY** "The alert that matters: a model call that stalls past 20 seconds. It fired on a real
run at 9:29 this morning. And every deal is a visible run — plan, read, rules, verify, compare,
decide, verify the quote, answer."

**SEE** E: the cluster list. F: the headline sentence. G: the fired alert under *Requires
attention*. H: the 12 steps.

## 2:45 — Live (10 s)

**CLICK** terminal, press Enter. Then tab I.

**SAY** "This is an eight-deal HubSpot export anyone can edit. It runs in twelve seconds. Fabrikam:
the contact left, a 'PO next week' that is 31 days old, and the sibling deal still lists her.
Every finding becomes a draft correction a human approves."

**SEE** the run finish; the live deal with its findings.

## 2:55 — Close (5 s)

**SAY** "A forecast without receipts is a guess with a nice spreadsheet. Ledger gives finance
the receipts — every Monday, and before the CFO signs."

---

## If asked

- **Is the data real?** The deals, amounts, dates and win/loss outcomes are real, from a
  public CRM dataset. The emails and notes are written by us, one story per deal based on its
  real outcome, with the problems planted and labelled. That is disclosed in the README. The
  live export is hand-written; edit a sentence and re-run it.
- **Why not just a better prompt, or a better model?** We measured both. Asking the same
  model to "find the issues" gets 32% recall and 17% false alarms on Gemini, 72% and 12% on
  Claude Sonnet. Better, still wrong. Ledger's model only reads into a schema; code compares.
- **Did you tune it to the labels?** No prompt or model change after scoring. We fixed five
  bugs in the comparison code and closed four label gaps; every one is listed in the README
  and FINDINGS.md with the before and after.
- **Isn't commit right by definition, since it just drops flagged deals?** Half right, and we
  measured it: with the exclusion rule 87% of committed dollars closed; without it, also 87%;
  the CRM's own stage-based commit, 64%. The accuracy is in the probabilities. The exclusion buys
  a number you can defend line by line, and on this data it cost $120K that closed, because the
  findings that predict loss already pull a deal below 70%. It is written up as finding 27 and
  the next step is to learn which findings predict loss from the company's own closed deals.
- **Would you ship this?** The findings tomorrow. The forecast number after a quarter of
  outcomes, or with a real decision model. The win probability today is the reading model
  asked a second question; it ranks well on our data and did not transfer to the independent
  SaaS data. We say so in the README.
- **Real CRMs?** HubSpot and Salesforce exports. Who said what comes from email direction and
  addresses. Ingest refuses an export where nothing is attributable to a buyer. Thresholds
  are learned from the company's closed deals.
- **Cost?** About $6 for 235 deals on Claude Sonnet through Nicrron; cents a week after that
  because unchanged records reuse their ledger. Free on a local model.
- **So PRISM found bugs in your agent?** In how it reported itself, yes: 470 runs clustered as
  failures because of our status semantics; two trajectory rules our auditor caught the same
  way. The findings it showed the manager were already verified. The real output bug today —
  five false alarms where the model called a condition a pause — came from our planted-anomaly
  score, and is fixed and logged. In September PRISM's PII guardrail caught phone numbers our
  paraphrase step had invented; that was a data failure PRISM found first.
- **What did PRISM not do well?** Forty-two items of feedback in docs/PRISM_FEEDBACK.md. The
  big three: Root Cause does nothing until someone presses Analyze, rule semantics are not
  documented, and alerts fire once and go quiet.

## Numbers card (glance at this, do not read it out)

| | naive agent | Ledger |
|---|---|---|
| semantic problems found (of those planted) | 72% | 94% |
| clean deals wrongly flagged | 10 of 86 | 0 of 86 |
| invented numbers | 6 | 0 |
| revenue in the top 20 | 64% | 71% |
| objection heard correctly | 68% | 95% |
| September, cheaper model: found / false alarms / invented | 32% / 17% / 97 | 92% / 0 / 0 |
| PRISM rules passing on Ledger runs | | 17 of 17 |
| findings fixed and re-proved today | | 26 in FINDINGS.md |

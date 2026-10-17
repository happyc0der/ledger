# Devpost fields — paste in order (AI x Fintech Hackathon - Money Talks 2)

## Step 2 · Project overview

**Project name** (≤ 60 chars)

Ledger — the revenue forecast with receipts

**Elevator pitch** (≤ 200 chars)

Reads what the buyer actually wrote on every deal, checks it in code against the CRM, and forecasts with a verified receipt behind every dollar — audited through PRISM, run through Nicrron.

**Thumbnail**: docs/screenshots/devpost_thumbnail.png (3:2, PNG).

## Step 3 · Project details

**Project story** (Devpost accepts Markdown)

### Inspiration
Every month a finance team signs a revenue forecast built from a CRM that reps fill in optimistically. The CRM's alerts only look at fields. The sentence that would change the number — "we've paused all new vendor onboarding", an auto-reply saying the champion left — sits in an email nobody re-reads.

### What it does
Ledger ingests a HubSpot or Salesforce export, resolves who said what, and has the model read each deal into a fixed claim ledger of buyer-stated facts with verbatim quotes. Code does everything else: a verifier drops any claim without a word-for-word quote, computes amounts and day gaps, and runs 18 checks (8 field rules, 10 semantic contradictions, including cross-deal) against the CRM. Out come a win probability, objection and next action per deal, every finding with the buyer's sentence, a commit / best-case forecast with every excluded dollar explained, draft CRM corrections a human approves, and Monday digests. Every model call is a PRISM trace; every deal is a PRISM run with visible check steps; an auditor reads PRISM back and attributes each failure to data, agent, guardrail or instrumentation.

### How we built it
Python, FastAPI, pandas; every model call through the Nicrron API (Claude Sonnet 5.5 on event day); PRISM for traces, runs, alerts and Root Cause; the same pipeline also runs on Gemini and on free local models (gemma4:12b, qwen3:14b). The benchmark is 235 real deals from the public Maven CRM dataset with real outcomes hidden from the agent; notes are synthetic and 18 anomaly types are planted and labelled, all disclosed.

### The proof (same 235 deals, outcomes hidden, event-day run on Claude Sonnet 5.5 via Nicrron)
CRM rules: 0% of the semantic problems. The same model asked to "find the issues": 72% recall, 10 of 86 clean deals falsely flagged, 6 invented numbers. Ledger: 94% recall, 99% precision, 0 of 86 clean deals flagged, 0 invented numbers; revenue in the top-20 64% → 71%; objection accuracy 68% → 95%. On a free 12B model on a laptop GPU: 80% recall, still 0 and 0. The floor does not depend on the model; the recall does.

### The three PRISM proofs (Money Operations)
1. Sessions → Steps: every deal is a 12-step run — plan, crm, rules, claim ledger, verification, checks, assessment, decide, quote verifier, final answer.
2. Alert: rules scoped to the agent (stalled call > 20 s, guardrail block, model returned nothing). "A model call returned nothing" fired on a real run where the gateway cut the answer off — the alert that would have caught that morning's failure; the stalled-call rule fired at 9:29.
3. Root Cause: the failure is the naive agent — its runs on the same deals cluster as failures with a cause (unsupported answers, no recovery; 8 traces analysed, then Analyze now); the fix is Ledger — same inputs, 17/17 trajectory rules pass. PRISM's own Agent Intelligence narrative on the naive agent: "Agent fabricates deal data on pipeline reviews … add guardrails to prevent deal fabrication."

### Challenges
Nicrron's 60 requests/minute cap, 4,096-token default output (empty content on truncation) and 30 s upstream timeout each broke a run before lunch; the client now rate-limits, streams and never caches an empty reply. PRISM's Root Cause clustered 470 of our own runs as failures because we had sent "error" to mean "this deal has a finding" — an instrumentation bug PRISM found, fixed and re-proved. A second model labelled a conditional objection as a pause; the check now demands pause language in the quote. All 27 failures, with evidence and re-proof, are in FINDINGS.md.

### What we learned
Reading scales with the model (37% → 80% → 92% → 94% → 95% recall across five readers); judgement does not (top-20 ranking 63–82% in no order of model size). A bigger reader does not buy a better judge, which is why the decision layer is designed to be a separate calibrated model. And the commit rule buys defensibility, not accuracy: measured against outcomes, excluding flagged deals removed $120K that closed — disclosed, not tuned away.

### What's next
A run on a real customer export; a calibrated decision model (Jev, waitlisted; the backend is wired); learning which finding types predict loss from a company's own closed deals; chunking for very long records.

**Built with** (tags): python, fastapi, pandas, nicrron, claude, prism, ollama, sqlite, pytest, ffmpeg

**"Try it out" links**
- https://github.com/happyc0der/ledger
- https://github.com/happyc0der/ledger/blob/master/DEMO.md
- https://github.com/happyc0der/ledger/blob/master/docs/SYSTEM_DESIGN.md
- https://github.com/happyc0der/ledger/blob/master/FINDINGS.md

**Video demo link**: Devpost wants YouTube or Vimeo. Upload docs/video/ledger_demo_backup.mp4 (98 s) as *unlisted* on YouTube and paste the link. Until then the file is at https://github.com/happyc0der/ledger/blob/master/docs/video/ledger_demo_backup.mp4

## Step 4 · Additional info (typical fields)
- Track: Money Operations
- Built with PRISM: yes — three proofs above; 42 items of product feedback in docs/PRISM_FEEDBACK.md
- Built with Nicrron: yes — every model call on event day (`LLM_PROVIDER=nicrron`), notes in docs/NICRRON_NOTES.md
- Team: solo — Keshav Rajput (happyc0der)
- Repo visibility: public

## Step 5 · Submit
Check the preview once, then submit before 4:00 PM.

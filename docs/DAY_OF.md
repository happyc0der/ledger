# Day-of checklist — Saturday Oct 17

**Before leaving**
- Laptop charged; phone hotspot tested; Ollama running on the Mac (`ollama serve`); `qwen3:14b` is pulled and the template run is cached (Oct 16), so the live demo works with no network at all.
- `./scripts/demo_up.sh` → **8787 = the event run (Sonnet 5.5 via Nicrron)**, 8788 = live, 8789 = the September Gemini run; PRISM live_connected; Nicrron balance line; Ollama mac OK. Ollama msi OK is a bonus (GPU: the 8-deal template cold in 60 s vs 122 s on the Mac, measured Oct 16) and needs the laptop awake on Tailscale.
- Hard-reload the :8787 tab once (the Proof-tab fix of Oct 17 10:55 must be the version in the browser), then open the tabs in order: proof · deal P9VFKNR0 · sibling OEBJXZN6 · naive v1 · PRISM traces (Flagged, 30 days) · PRISM runs · live 8788 deal 2003 · digest. Backup video open in a player.
- PRISM dashboard logged in (in the browser you'll present from).
- `.env` holds a free-tier Gemini key (new project, no billing; verified Oct 16) with the estimated-spend cap at $20 — the key cannot bill anything. Stage default is `LLM_PROVIDER=gemini`; a 429 from the free tier or a 5xx falls over to the Mac mid-run. Untouched template → under 1 s from cache on every path; an edited 8-deal CSV → about 1.5 min on the free-tier Gemini key (measured Oct 16: 16 calls, median 4 s, one 39 s outlier, no fallback), 1 min on msi, 2 min on the Mac.

**The three Money Operations PRISM proofs (required by the Builder Resource Pack)**
1. Sessions → Steps: https://prism.blockconvey.com/sessions/v3-Niesha_Huffines-sonnet → *Steps* tab shows the 12-step
   ledger-v3 run from the event morning (plan · crm · rules · claim ledger · verification · checks · assessment · decide · verifier:quote · final_answer).
   Screenshot: docs/screenshots/prism_14_session_steps.jpg.
2. Alert: https://prism.blockconvey.com/alerts — rules scoped to agent `ledger`: *model call stalled (>20 s)* and
   *prompt blocked by a guardrail*; plus the older *trace failures per hour* rule. **Fired on a real run on Oct 17,
   09:29 ET**: *model call stalled* — latency 25,942 ms vs 20,000 on a naive-agent batch call (trace `5c55f46f…`), and
   *trace failures per hour* 6/5 at 09:29:40 (the empty replies of finding 20). Both sit under "Requires attention"
   on the Alerts page; screenshot docs/screenshots/prism_15_alert_fired.jpg.
3. Root Cause / Agent Intelligence. **Lead with the naive agent as the failure and Ledger as the fix** — same 235
   inputs, same model: cluster `a986c666…` *failures in ledger-v1* (7 runs on Oct 17, cause: unsupported answers,
   no recovery; human-verified “prompt”) vs ledger-v3 runs on the same deals passing 17/17 rules. The recipe's
   per-trace step was done on 8 of this morning's naive traces (Analyse selected) before Analyze now. The
   instrumentation story (finding 18) is the aside, not the proof: say it as “PRISM also caught us mislabelling
   our runs; we fixed the reporting”. After per-trace analysis of the 52 naive-agent traces (52 credits), PRISM's own
   narrative (docs/prism_intelligence_narrative.json, generated Oct 17 13:40 UTC) reads: **"Agent fabricates deal data on
   pipeline reviews, undermining sales forecasting reliability"** — "the agent resolves only 1 of 15 such requests fully.
   Five of six documented failures involve hallucinated deal IDs, buyer quotes, and metrics absent from source data" — top
   action: **"add guardrails to prevent deal fabrication"**. That is the v3 design, in PRISM's words.
   Root Cause: https://prism.blockconvey.com/root-cause — cluster `a986c666…` *failures in ledger-v1* (7 runs on Oct 17 incl. the clean Sonnet run, rising, cause: tool — the post-hoc `check:*:mismatch` steps) beside the
   `ledger-v3` cluster whose last failure is Oct 16 14:45 UTC — nothing after the fix; both carry a human-verified cause
   (code / prompt) recorded via the review endpoint. Repo connected (Connectors → Code repository): PRISM localised four
   small clusters to candidate files (`ledger/agent_v1.py`, `ledger/claims.py`, `ledger/decide.py`) and suspect commits; the
   big trajectory-only clusters are not localised by design (feedback #42) — say so if asked. After today's run: the `ledger-v1` cluster (unsupported answers:
   fabricated quotes / amounts / day gaps caught by the post-hoc checks) and `ledger-v3` on the same deals no longer failing
   (finding 18 in FINDINGS.md explains why the v3 cluster existed before). Re-run clustering after the runs:
   `POST $PRISM_HOST/api/intelligence/clusters/analyze` (5 credits).

**At the venue**
- Ask for the rules (pre-built code) and the Discord; if a from-scratch rebuild is required, follow docs/REBUILD.md and `scripts/day.sh` with a fresh PRISM project.
- If PRISM is slow, the SDK's timeouts can stall a run: set `PRISM_DISABLED=1` for any live run and show the existing traces instead.

**Submission** — docs/SUBMISSION.md is paste-ready; repo https://github.com/happyc0der/ledger (make public before submitting if judges need to open it).

**Answers to have ready** — synthetic notes (disclosed; naive agent reads the same notes and gets 32%); planted labels vs real outcomes; "did you tune to the labels" (no prompt changes after scoring; FINDINGS.md lists every comparison fix); Jev not integrated (waitlist; `decide.py` switches on the key); cost (~$0.35/run on Gemini, free locally).

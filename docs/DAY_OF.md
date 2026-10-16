# Day-of checklist — Saturday Oct 17

**Before leaving**
- Laptop charged; phone hotspot tested; Ollama running on the Mac (`ollama serve`); `qwen3:14b` is pulled and the template run is cached (Oct 16), so the live demo works with no network at all.
- `./scripts/demo_up.sh` → 8787, 8788, PRISM live_connected, Ollama mac OK. Ollama msi OK is a bonus (GPU: the 8-deal template cold in 60 s vs 122 s on the Mac, measured Oct 16) and needs the laptop awake on Tailscale.
- Browser tabs in order: proof · deal P9VFKNR0 · sibling OEBJXZN6 · naive v1 · PRISM traces (Flagged, 30 days) · PRISM runs · live 8788 deal 2003 · digest. Backup video open in a player.
- PRISM dashboard logged in (in the browser you'll present from).
- `.env` holds a free-tier Gemini key (new project, no billing; verified Oct 16) with the estimated-spend cap at $20 — the key cannot bill anything. Stage default is `LLM_PROVIDER=gemini`; a 429 from the free tier or a 5xx falls over to the Mac mid-run. Untouched template → under 1 s from cache on every path; an edited 8-deal CSV → about 1.5 min on the free-tier Gemini key (measured Oct 16: 16 calls, median 4 s, one 39 s outlier, no fallback), 1 min on msi, 2 min on the Mac.

**At the venue**
- Ask for the rules (pre-built code) and the Discord; if a from-scratch rebuild is required, follow docs/REBUILD.md and `scripts/day.sh` with a fresh PRISM project.
- If PRISM is slow, the SDK's timeouts can stall a run: set `PRISM_DISABLED=1` for any live run and show the existing traces instead.

**Submission** — docs/SUBMISSION.md is paste-ready; repo https://github.com/happyc0der/ledger (make public before submitting if judges need to open it).

**Answers to have ready** — synthetic notes (disclosed; naive agent reads the same notes and gets 32%); planted labels vs real outcomes; "did you tune to the labels" (no prompt changes after scoring; FINDINGS.md lists every comparison fix); Jev not integrated (waitlist; `decide.py` switches on the key); cost (~$0.35/run on Gemini, free locally).

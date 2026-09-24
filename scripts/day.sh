#!/bin/sh
# Hackathon-day pipeline. Spends the PRISM free quota on the traces the demo shows.
set -e
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
export LLM_PROVIDER=${LLM_PROVIDER:-gemini}
.venv/bin/python scripts/prism_smoke.py
./scripts/make_data.sh
.venv/bin/python scripts/run.py v1 --reps "Darcel Schlecht"          # PRISM on: the failing baseline, one rep
PRISM_DISABLED=1 .venv/bin/python scripts/run.py v1                    # rest of the team, quota-free
PRISM_DISABLED=1 .venv/bin/python scripts/run.py naive
.venv/bin/python scripts/run.py v3 --reps "Darcel Schlecht"          # PRISM on: trajectories with check:* steps
PRISM_DISABLED=1 .venv/bin/python scripts/run.py v3
.venv/bin/python scripts/run.py eval v1 v3
.venv/bin/python scripts/run.py issues v3 naive
.venv/bin/python scripts/run.py audit --hours 6
.venv/bin/python scripts/run.py digest
echo "UI: .venv/bin/uvicorn ledger.app:app --port 8787"

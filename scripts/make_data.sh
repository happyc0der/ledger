#!/bin/sh
# Rebuild the demo company from scratch: base stories -> paraphrase (cached) -> planted anomalies.
set -e
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
rm -f data/company/activities_original.csv
.venv/bin/python scripts/build_company.py | tail -1
LLM_PROVIDER=${PARAPHRASE_PROVIDER:-gemini} PRISM_DISABLED=1 .venv/bin/python scripts/paraphrase.py | tail -1
.venv/bin/python scripts/plant_anomalies.py

#!/bin/sh
# Stage setup in one command: both UIs up, PRISM live, bookmark URLs printed.
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
pkill -f "uvicorn ledger.app" 2>/dev/null; sleep 1
mkdir -p runs/company runs/live
nohup .venv/bin/uvicorn ledger.app:app --port 8787 > runs/company/ui.log 2>&1 &
LEDGER_DATA=data/live nohup .venv/bin/uvicorn ledger.app:app --port 8788 > runs/live/ui.log 2>&1 &
sleep 3
printf "benchmark UI  %s\n" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8787/api/meta)"
printf "live UI       %s\n" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8788/api/meta)"
printf "PRISM         %s\n" "$(curl -sS -m 15 "$PRISM_HOST/api/setup-doctor?project_id=$PRISM_PROJECT_ID" -H "X-PRISMtrace-Key: $PRISM_API_KEY" | .venv/bin/python -c 'import json,sys; d=json.load(sys.stdin); print(d.get("overall"), "live_connected", d.get("live_connected"))' 2>/dev/null || echo unreachable)"
ollama_check() {  # label, base url, model -> OK | NO MODEL | down
  tags=$(curl -s -m 5 "$2/api/tags" 2>/dev/null) || tags=""
  case "$tags" in
    *"\"$3\""*) printf "Ollama %-5s OK        %s has %s\n" "$1" "$2" "$3" ;;
    "")          printf "Ollama %-5s down      %s\n" "$1" "$2" ;;
    *)           printf "Ollama %-5s NO MODEL  %s lacks %s -> ollama pull %s\n" "$1" "$2" "$3" "$3" ;;
  esac
}
ollama_check mac http://localhost:11434 qwen3:14b
ollama_check msi http://msi:11434 gemma4:12b
cat <<URLS

Stage bookmarks
  0:20  proof           http://localhost:8787/?view=proof
  0:40  the deal        http://localhost:8787/?deal=P9VFKNR0
  1:25  sibling         http://localhost:8787/?deal=OEBJXZN6
  1:40  naive on same   http://localhost:8787/?version=v1&deal=P9VFKNR0
  2:15  PRISM traces    https://prism.blockconvey.com/traces   (status: Flagged, range: 30 days)
        PRISM runs      https://prism.blockconvey.com/trajectories
  2:35  live export     http://localhost:8788/?deal=2003
        digest          http://localhost:8787/?digest=1
  live run (pick one; the untouched template is cached for all three -> instant):
    Mac, offline:   LLM_PROVIDER=ollama PRISM_DISABLED=1 .venv/bin/python scripts/live.py --preset hubspot --deals data/templates/hubspot_deals.csv --activities data/templates/hubspot_engagements.csv --contacts data/templates/hubspot_contacts.csv --products data/company/products.csv --as-of 2026-10-19
    msi GPU (awake, Tailscale):  prefix the same command with OLLAMA_URL=http://msi:11434 OLLAMA_MODEL=gemma4:12b
    Gemini (only with a billing-free key in .env):  LLM_PROVIDER=gemini ...  (a dead key falls back to the Mac automatically)
URLS

#!/bin/sh
# Stage setup in one command: both UIs up, PRISM live, bookmark URLs printed.
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
pkill -f "uvicorn ledger.app" 2>/dev/null; sleep 1
mkdir -p runs/company runs/live runs/company_nicrron
# :8787 = the event run (Claude Sonnet 5.5 through Nicrron, as the organisers require); :8789 = the September Gemini run
LEDGER_DATA=data/company_nicrron nohup .venv/bin/uvicorn ledger.app:app --port 8787 > runs/company_nicrron/ui.log 2>&1 &
LEDGER_DATA=data/live nohup .venv/bin/uvicorn ledger.app:app --port 8788 > runs/live/ui.log 2>&1 &
nohup .venv/bin/uvicorn ledger.app:app --port 8789 > runs/company/ui.log 2>&1 &
sleep 3
printf "stage UI      %s  (http://localhost:8787, Sonnet 5.5 via Nicrron)\n" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8787/api/meta)"
printf "live UI       %s  (http://localhost:8788)\n" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8788/api/meta)"
printf "gemini UI     %s  (http://localhost:8789, September run)\n" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8789/api/meta)"
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
if [ -n "$NICRRON_API_KEY" ]; then
  nic=$(curl -s -m 10 https://api.nicrron.ai/v1/key -H "Authorization: Bearer $NICRRON_API_KEY" | .venv/bin/python -c 'import json,sys,os; d=json.load(sys.stdin)["data"]; print("balance $%.2f, used $%.2f, %s req/%s; cap NICRRON_BUDGET_USD=%s" % (d["balance"], d["usage"], d["rate_limit"]["requests"], d["rate_limit"]["interval"], os.getenv("NICRRON_BUDGET_USD", "200")))' 2>/dev/null || echo down)
  printf "Nicrron       %s  (%s)\n" "$nic" "${NICRRON_MODEL:-anthropic/claude-sonnet-5-5}"
else
  printf "Nicrron       NO KEY  (NICRRON_API_KEY missing in .env; organisers require model calls through Nicrron)\n"
fi
cat <<URLS

Stage bookmarks
  0:20  proof           http://localhost:8787/?view=proof
  0:40  the deal        http://localhost:8787/?deal=P9VFKNR0
  1:25  sibling         http://localhost:8787/?deal=OEBJXZN6
  1:40  naive on same   http://localhost:8787/?version=v1&deal=P9VFKNR0
  2:15  PRISM traces    https://prism.blockconvey.com/traces   (status: Flagged, range: 30 days)
        PRISM runs      https://prism.blockconvey.com/trajectories
        proof 1 steps   https://prism.blockconvey.com/sessions/v3-Niesha_Huffines-sonnet   (Steps tab)
        proof 2 alert   https://prism.blockconvey.com/alerts
        proof 3 cause   https://prism.blockconvey.com/root-cause
        intelligence    https://prism.blockconvey.com/intelligence   (PRISM's own narrative on the naive agent)
  2:35  live export     http://localhost:8788/?deal=2003
        digest          http://localhost:8787/?digest=1
  live run (the untouched template is cached on every path -> instant):
    default (event requirement: Nicrron; 429/5xx fall back to the Mac automatically):
      LLM_PROVIDER=nicrron .venv/bin/python scripts/live.py --preset hubspot --deals data/templates/hubspot_deals.csv --activities data/templates/hubspot_engagements.csv --contacts data/templates/hubspot_contacts.csv --products data/company/products.csv --as-of 2026-10-19
    Gemini:      same command with LLM_PROVIDER=gemini   (free-tier key, ~1.5 min cold)
    no network:  same command with LLM_PROVIDER=ollama PRISM_DISABLED=1   (Mac qwen3:14b, 8 deals ~2 min cold)
    GPU:         prefix with OLLAMA_URL=http://msi:11434 OLLAMA_MODEL=gemma4:12b LLM_PROVIDER=ollama   (msi awake on Tailscale, ~1 min cold)
URLS

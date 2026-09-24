"""The live run: a CSV export in, findings with receipts out, in under a minute.

  scripts/live.py --preset hubspot --deals deals.csv --activities engagements.csv [--contacts c.csv] \\
      [--products data/company/products.csv] --name live --as-of 2026-10-19 [--limit 30]

Ingests into data/<name>/, runs Ledger v3 with a thread pool (per-deal work is independent until
the cross-deal pass), then the auditor. Prints the findings and where the UI can be pointed:
  LEDGER_DATA=data/<name> .venv/bin/uvicorn ledger.app:app --port 8788
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ap = argparse.ArgumentParser()
ap.add_argument("--preset", default="hubspot"); ap.add_argument("--deals", required=True); ap.add_argument("--activities")
ap.add_argument("--contacts"); ap.add_argument("--products"); ap.add_argument("--name", default="live")
ap.add_argument("--as-of", default=None); ap.add_argument("--limit", type=int, default=30); ap.add_argument("--workers", type=int, default=8)
ap.add_argument("--company", default="Live export")
a = ap.parse_args()

out = ROOT / "data" / a.name
os.environ["LEDGER_DATA"] = str(out)
if a.as_of:
    os.environ["LEDGER_AS_OF"] = a.as_of
from ledger.ingest import ingest  # noqa: E402

t0 = time.time()
rep = ingest(a.preset, out, deals=Path(a.deals), activities=Path(a.activities) if a.activities else None,
             contacts=Path(a.contacts) if a.contacts else None, products=Path(a.products) if a.products else None, company=a.company)
print(f"ingested {rep['deals']['rows'] - rep['deals']['dropped_closed']} open deals, attribution {rep.get('attribution')}  ({time.time() - t0:.1f}s)")

# import after LEDGER_DATA is set: config binds the dataset at import time
from ledger import audit, evaluate, store, tracing  # noqa: E402
from ledger.agent_v3 import _previous_ledgers, team_cross_deal  # noqa: E402
from ledger.agent_v3 import run_rep  # noqa: E402
from ledger.config import RUNS_DIR, SNAPSHOT  # noqa: E402
from ledger.data import load_company  # noqa: E402

co = load_company()
deals = co.deals.head(a.limit)
reps = sorted(deals.sales_agent.unique())
t1 = time.time()


def one(rep_name):
    return run_rep(co, rep_name, limit=None)


rows = []
with ThreadPoolExecutor(max_workers=min(a.workers, max(len(reps), 1))) as ex:
    for part in ex.map(one, reps):
        rows += [r for r in part if r["opportunity_id"] in set(deals.opportunity_id)]
rows = team_cross_deal(co, rows)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
(RUNS_DIR / "v3.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))
run_id = store.record_run(rows, as_of=SNAPSHOT, version="v3", provider=os.getenv("LLM_PROVIDER", "gemini"),
                          decide_backend=next((r.get("decision_backend") for r in rows), ""), deals=co.deals)
print(f"ran Ledger on {len(rows)} deals in {time.time() - t1:.1f}s  (run {run_id})")
fs = audit.run(co, ("v3",), hours=1, prism=os.getenv("PRISM_DISABLED") != "1", partial=True)
audit.report(fs, label=f"audit_{a.name}")

n_issues = sum(len(r["issues"]) for r in rows)
print(f"\n{n_issues} findings on {sum(1 for r in rows if r['issues'])} deals:")
for r in sorted(rows, key=lambda r: -len(r["issues"]))[:12]:
    if r["issues"]:
        d = co.deal(r["opportunity_id"])
        print(f"\n  {d.account} · {d['product']} · {d.stage} · p={r['win_probability']:.2f} → {r['next_action']}")
        for i in r["issues"]:
            print(f"    - {i['type']}: {i['detail'][:90]}" + (f"\n        “{i['evidence'][:100]}”" if i.get("evidence") and "=" not in i["evidence"] else ""))
print(f"\naudit: {len(fs)} findings ({sum(f.severity == 'high' for f in fs)} high) -> reports/audit_{a.name}.md")
print(f"\nUI:  LEDGER_DATA={out.relative_to(ROOT)} .venv/bin/uvicorn ledger.app:app --port 8788")

"""CLI for ledger.ingest. Example:
  scripts/ingest.py --preset hubspot --deals ~/Downloads/deals.csv --activities ~/Downloads/engagements.csv --out data/acme --company "Acme"
Then: LEDGER_DATA=data/acme scripts/run.py v3
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ledger.ingest import ingest  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--preset", default="hubspot", choices=["hubspot", "salesforce", "ledger"])
ap.add_argument("--deals", required=True); ap.add_argument("--activities"); ap.add_argument("--contacts")
ap.add_argument("--products"); ap.add_argument("--team"); ap.add_argument("--mapping", help="JSON file with column overrides")
ap.add_argument("--out", required=True); ap.add_argument("--company", default="Your company")
ap.add_argument("--allow-no-buyer", action="store_true", help="proceed even if no activity can be attributed to a buyer (rules only)")
a = ap.parse_args()
rep = ingest(a.preset, Path(a.out), deals=Path(a.deals), activities=Path(a.activities) if a.activities else None,
             contacts=Path(a.contacts) if a.contacts else None, products=Path(a.products) if a.products else None,
             team=Path(a.team) if a.team else None, mapping=json.load(open(a.mapping)) if a.mapping else None, company=a.company, allow_no_buyer=a.allow_no_buyer)
print(json.dumps(rep, indent=1, default=str))

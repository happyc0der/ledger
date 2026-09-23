"""Run a version of the agent over the demo team and write runs/<version>.jsonl.

  .venv/bin/python scripts/run.py v1 --reps "Marty Freudenburg" --limit 10
  .venv/bin/python scripts/run.py v1                      # whole team
  .venv/bin/python scripts/run.py eval v1 v2              # comparison table
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ledger import evaluate  # noqa: E402
from ledger.config import RUNS_DIR  # noqa: E402
from ledger.data import load_company  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("more", nargs="*")
    ap.add_argument("--reps", default=None, help="comma-separated rep names")
    ap.add_argument("--limit", type=int, default=None, help="deals per rep")
    ap.add_argument("--activities", default=None, help="audit: alternative activities.csv to inspect")
    ap.add_argument("--hours", type=int, default=24, help="audit: how far back to read PRISM")
    ap.add_argument("--no-prism", action="store_true", help="audit: skip PRISM reads")
    ap.add_argument("--label", default="audit", help="audit: report name under reports/")
    a = ap.parse_args()
    co = load_company()

    if a.version == "eval":
        print(evaluate.report(co, a.more))
        return
    if a.version == "audit":
        from ledger import audit
        fs = audit.run(co, a.more or ("v1", "v2"), activities_path=a.activities, hours=a.hours, prism=not a.no_prism)
        print(audit.report(fs, label=a.label))
        return

    if a.version == "issues":  # score rules vs agent findings against planted anomalies
        from ledger import score_issues
        from ledger.rules import Issue, run_rules
        ids = list(co.deals.opportunity_id)
        scores = [score_issues.score(run_rules(co), ids, "rules")]
        for ver in a.more or ["v3"]:
            p = RUNS_DIR / f"{ver}.jsonl"
            if p.exists():
                rows = [json.loads(l) for l in p.read_text().splitlines()]
                iss = [Issue(**{k: v for k, v in i.items() if k in Issue.__dataclass_fields__}) for r in rows for i in r.get("issues", [])]
                scores.append(score_issues.score(iss, ids, ver))
        md = score_issues.table(scores)
        Path("reports").mkdir(exist_ok=True); Path("reports/issues.md").write_text(md); print(md)
        return

    if a.version == "v1":
        from ledger.agent_v1 import run_rep
    elif a.version == "v3":
        from ledger.agent_v3 import run_rep
    else:
        from ledger.agent_v2 import run_rep

    reps = a.reps.split(",") if a.reps else co.reps()
    RUNS_DIR.mkdir(exist_ok=True)
    out = RUNS_DIR / f"{a.version}.jsonl"
    out.write_text("")
    n = 0
    for rep in reps:  # written after every rep so a crash keeps what was done
        t0 = time.time()
        r = run_rep(co, rep, limit=a.limit)
        with out.open("a") as f:
            f.write("\n".join(json.dumps(x) for x in r) + "\n")
        n += len(r)
        print(f"{rep}: {len(r)} deals in {time.time() - t0:.0f}s", flush=True)
    if a.version == "v3":  # cross-deal checks across the whole team, then rewrite
        from ledger.agent_v3 import team_cross_deal
        rows = team_cross_deal(co, [json.loads(l) for l in out.read_text().splitlines()])
        out.write_text("\n".join(json.dumps(r, default=str) for r in rows) + "\n")
    print(f"wrote {n} rows -> {out}")


if __name__ == "__main__":
    main()

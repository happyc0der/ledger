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
    a = ap.parse_args()
    co = load_company()

    if a.version == "eval":
        print(evaluate.report(co, a.more))
        return

    if a.version == "v1":
        from ledger.agent_v1 import run_rep
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
    print(f"wrote {n} rows -> {out}")


if __name__ == "__main__":
    main()

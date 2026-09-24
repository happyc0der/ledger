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

import os  # noqa: E402

from ledger import evaluate, store  # noqa: E402
from ledger.config import RUNS_DIR, SNAPSHOT, run_dir  # noqa: E402
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
    ap.add_argument("--recompute", action="store_true", help="issues: rebuild v3 issues from stored ledgers (no model calls)")
    a = ap.parse_args()
    co = load_company()

    if a.version == "eval":
        print(evaluate.report(co, a.more))
        return
    if a.version == "digest":  # reports/<dataset>/<as_of>/digest_<name>.md for every rep + the manager
        from ledger import digest, forecast, history
        rows = digest.enrich(evaluate.load_rows("v3"), co.deals); rid = store.latest_run_id("v3")
        hist = history.summary(rid) if rid else {}
        fc = forecast.rollup(rows, backend=next((r.get("decision_backend") for r in rows if r.get("decision_backend")), "llm"), states=store.issue_states())
        outd = Path("reports") / store.DATASET / str(SNAPSHOT.date())
        outd.mkdir(parents=True, exist_ok=True)
        for rep in co.reps():
            (outd / f"digest_{rep.replace(' ', '_')}.md").write_text(digest.rep_digest(rep, rows, hist, fc, str(SNAPSHOT.date())))
        (outd / "digest_manager.md").write_text(digest.manager_digest(rows, hist, fc, str(SNAPSHOT.date()), co.reps()))
        print(f"wrote {len(co.reps()) + 1} digests -> {outd}"); print((outd / "digest_manager.md").read_text()[:1200])
        return
    if a.version == "export-approved":
        from ledger import proposals
        preset = (a.more or ["hubspot"])[0]
        outp = Path("reports") / store.DATASET / f"approved_updates_{preset}.csv"; outp.parent.mkdir(parents=True, exist_ok=True)
        df = proposals.export_approved(preset, outp); print(f"{len(df)} approved updates -> {outp}"); return
    if a.version == "agree":  # extraction agreement without labels: re-extract a sample uncached and compare slots
        import random
        from ledger import claims
        rows = evaluate.load_rows("v3"); random.Random(1).shuffle(rows)
        sample = rows[: a.limit or 40]
        slots = [k for k in claims.SLOTS if k != "_hints"]
        agree = {k: [0, 0] for k in slots}
        for r in sample:
            base = r["ledger"]
            again = claims.extract_uncached(co, r["opportunity_id"], version="agree", session="agree")
            for k in slots:
                agree[k][1] += 1
                agree[k][0] += int((base.get(k) in (None, "unknown", "none_mentioned", "none", "n/a")) == (again.get(k) in (None, "unknown", "none_mentioned", "none", "n/a")) and (str(base.get(k)).lower() == str(again.get(k)).lower()))
        md = ["# Extraction agreement (same model, uncached re-run, n=%d)" % len(sample), "", "| slot | agreement |", "|---|---|"] + \
             [f"| {k} | {v[0] / max(v[1], 1):.0%}{' ⚠' if v[0] / max(v[1], 1) < 0.7 else ''} |" for k, v in agree.items()]
        Path("reports").mkdir(exist_ok=True); Path("reports/agreement.md").write_text("\n".join(md)); print("\n".join(md)); return
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
                rows = evaluate.load_rows(ver)
                if a.recompute and all("ledger" in r for r in rows):  # only versions that carry a claim ledger
                    from dataclasses import asdict
                    from ledger.consistency import compare, cross_deal
                    by = {r["opportunity_id"]: r for r in rows}
                    rb = {}
                    for i in run_rules(co):
                        rb.setdefault(i.opportunity_id, []).append(asdict(i))
                    ledgers = {}
                    for r in rows:
                        lg = {**r["ledger"], "quotes": r["ledger_quotes"]}
                        ledgers[r["opportunity_id"]] = lg
                        r["issues"] = rb.get(r["opportunity_id"], []) + [asdict(x) for x in compare(co, r["opportunity_id"], lg)]
                    for x in cross_deal(co, ledgers):
                        by[x.opportunity_id]["issues"].append(asdict(x))
                    p.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))
                iss = [Issue(**{k: v for k, v in i.items() if k in Issue.__dataclass_fields__}) for r in rows for i in r.get("issues", [])]
                scores.append(score_issues.score(iss, ids, ver))
        md = score_issues.table(scores)
        Path("reports").mkdir(exist_ok=True); Path("reports/issues.md").write_text(md); print(md)
        return

    if a.version == "v1":
        from ledger.agent_v1 import run_rep
    elif a.version == "v3":
        from ledger.agent_v3 import run_rep
    elif a.version == "naive":
        from ledger.agent_naive_issues import run_rep
    else:
        from ledger.agent_v2 import run_rep

    reps = a.reps.split(",") if a.reps else co.reps()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out = RUNS_DIR / f"{a.version}.jsonl"
    out.write_text("")
    n = 0
    for rep in reps:  # written after every rep so a crash keeps what was done
        t0 = time.time()
        r = run_rep(co, rep, limit=a.limit)
        with out.open("a") as f:
            for x in r:
                f.write(json.dumps(x, default=str) + "\n")
        n += len(r)
        print(f"{rep}: {len(r)} deals in {time.time() - t0:.0f}s", flush=True)
    if a.version == "v3":  # cross-deal checks across the whole team, then rewrite
        from ledger.agent_v3 import team_cross_deal
        rows = team_cross_deal(co, evaluate.load_rows(a.version))
        out.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))
    rows = evaluate.load_rows(a.version)
    # per-dataset, per-review-date copy + the store (history, lifecycle, proposals)
    rd = run_dir(SNAPSHOT, a.version); rd.mkdir(parents=True, exist_ok=True)
    (rd / f"{a.version}.jsonl").write_text(out.read_text())
    backend = next((r.get("decision_backend") for r in rows if r.get("decision_backend")), "")
    run_id = store.record_run(rows, as_of=SNAPSHOT, version=a.version, provider=os.getenv("LLM_PROVIDER", "ollama"),
                              decide_backend=backend, deals=co.deals)
    print(f"wrote {n} rows -> {out}  (run {run_id} in {store.DB_PATH})")
    # the auditor runs after every agent run: PRISM flags/rules + stated-vs-computed + evidence validity
    if not a.no_prism or True:
        from ledger import audit
        fs = audit.run(co, (a.version,), hours=2, prism=os.getenv("PRISM_DISABLED") != "1", partial=bool(a.reps or a.limit))
        audit.report(fs, label=f"audit_{a.version}")
        hi = [f for f in fs if f.severity == "high"]
        print(f"audit: {len(fs)} findings, {len(hi)} high -> reports/audit_{a.version}.md" + ("".join(f"\n  ! {f.title}" for f in hi[:5])))


if __name__ == "__main__":
    main()

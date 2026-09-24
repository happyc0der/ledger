"""The auditor: an agent that finds the failures instead of a human reading traces.

It uses only what an operator could see in production — PRISM traces, guardrail flags,
trajectory rule results, the agent's own output and the CRM — never ground truth. Every
finding carries evidence (trace ids, deal ids, matched text), a source attribution
(data vs agent vs instrumentation) and a suggested fix, and the audit run itself is
submitted to PRISM as a trajectory so the discovery is observable too.

    scripts/run.py audit                # current runs + last 24h of PRISM
    scripts/run.py audit --hours 72 --activities path/to/other_activities.csv
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pandas as pd

from . import tracing
from .config import BASE_WIN_RATE, ROOT, RUNS_DIR
from .data import Company
from .tools import days_since_buyer_touch, deal_amount, normalize_product, pipeline_total

PII = {"email": r"[\w.+-]+@[\w-]+\.\w+", "phone": r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
       "clock time": r"\b\d{1,2}:\d{2}\s?(?:am|pm)?\b", "relative": r"\b(?:sister|brother|wife|husband|mother|father)\b"}
GENERIC_ACTIONS = {"re_engage_dormant"}


@dataclass
class Finding:
    check: str
    severity: str            # high | medium | low | info
    source: str              # data | agent | instrumentation | guardrail
    title: str
    count: int = 0
    evidence: list[str] = field(default_factory=list)
    fix: str = ""

    def md(self) -> str:
        ev = "".join(f"\n  - {e}" for e in self.evidence[:6])
        more = f"\n  - … {len(self.evidence) - 6} more" if len(self.evidence) > 6 else ""
        return f"- **[{self.severity}] {self.title}** _(source: {self.source}, check: {self.check})_{ev}{more}\n  - fix: {self.fix}"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower().replace("’", "'")).strip()


# ----------------------------------------------------------------------------- data
def check_data_hygiene(co: Company, activities: pd.DataFrame) -> list[Finding]:
    out = []
    if "speaker" in activities.columns and len(activities):
        vc = activities.speaker.value_counts()
        unk = vc.get("unknown", 0) / len(activities)
        if vc.get("buyer", 0) == 0:
            out.append(Finding("attribution", "high", "data", "No activity is attributable to a buyer — every claim will be dropped and the agent will find nothing",
                               len(activities), [f"speakers: {vc.to_dict()}"], "Export email direction / from-address columns, or a contacts file with names."))
        elif unk > 0.3:
            out.append(Finding("attribution", "medium", "data", f"{unk:.0%} of activities have no attributable speaker", int(vc.get("unknown", 0)),
                               [f"speakers: {vc.to_dict()}"], "Those rows cannot carry buyer evidence; add direction or contact data."))
    for name, pat in PII.items():
        hits = activities[activities.text.str.contains(pat, case=False, regex=True, na=False)]
        if len(hits):
            out.append(Finding("data_hygiene", "high" if name in ("email", "phone") else "medium", "data",
                               f"Notes contain {name} that the CRM has no field for ({len(hits)} activities)", len(hits),
                               [f"{r.activity_id}: {re.search(pat, r.text, re.I).group(0)!r} in “{r.text[:70]}…”" for r in hits.itertuples()],
                               "Content was added by a generation/paraphrase step; validate that rewrites add no facts, "
                               "and redact before the agent sees it."))
    known = {str(x) for x in (set(co.contacts.name) | set(co.deals.sales_agent) | set(co.team.manager) | set(co.deals.account)) if isinstance(x, str)}
    known_tokens = {w for n in known for w in n.split()} | {w for p in co.products["product"] if isinstance(p, str) for w in p.split()}
    mentions, deals_per = Counter(), defaultdict(set)
    for r in activities.itertuples():
        for m in re.finditer(r"\b([A-Z][a-z]+) ([A-Z][a-z]+)\b", r.text):
            before = r.text[max(0, m.start() - 2):m.start()]
            if m.start() == 0 or re.search(r"[.!?]\s?$|^\s*$", before):
                continue  # sentence start: capitalised for grammar, not a name
            if m.group(1) not in known_tokens and m.group(2) not in known_tokens:
                mentions[m.group(0)] += 1
                deals_per[m.group(0)].add(r.opportunity_id)
    recurring = {k: v for k, v in mentions.items() if len(deals_per[k]) >= 5}
    rare = {k: v for k, v in mentions.items() if len(deals_per[k]) < 5}
    if rare:
        out.append(Finding("data_hygiene", "medium", "data", f"Notes mention people/companies unknown to the CRM ({len(rare)} distinct, each in <5 deals)",
                           sum(rare.values()), [f"{k} ×{v}" for k, v in Counter(rare).most_common(8)],
                           "Names that are in no contact, account or team record are usually hallucinated by a generation step."))
    if recurring:
        out.append(Finding("data_hygiene", "info", "data", f"Third parties recurring across deals but untracked in the CRM ({len(recurring)})", sum(recurring.values()),
                           [f"{k} ×{v} across {len(deals_per[k])} deals" for k, v in Counter(recurring).most_common(5)],
                           "Probably competitors; add a competitor field so the agent can reason about them explicitly."))
    return out


def check_catalogue(co: Company) -> list[Finding]:
    cat = {p: normalize_product(p) for p in co.products["product"]}
    out = []
    for prod, n in co.deals.groupby("product").size().items():
        if prod in cat:
            continue
        match = [p for p, k in cat.items() if k == normalize_product(prod)]
        if match:
            val = n * float(co.products.set_index("product").loc[match[0], "sales_price"])
            out.append(Finding("catalogue", "high", "data", f"Pipeline spells “{prod}” but the catalogue says “{match[0]}” — {n} deals, ${val:,.0f} at list",
                               n, [f"exact lookup fails; normalised lookup succeeds"],
                               "Normalise product names before any price lookup or total; never let the model do the join."))
        else:
            out.append(Finding("catalogue", "high", "data", f"Pipeline product “{prod}” has no catalogue entry at all ({n} deals)", n, [], "Fix the catalogue."))
    return out


# ----------------------------------------------------------------------------- agent output
def check_output(co: Company, version: str, partial: bool = False) -> list[Finding]:
    p = RUNS_DIR / f"{version}.jsonl"
    if not p.exists():
        return [Finding("output", "info", "agent", f"No run found for {version}")]
    rows = pd.DataFrame([json.loads(l) for l in p.read_text().splitlines() if l.strip()])
    out, ids = [], set(co.deals.opportunity_id)
    dup, phantom = rows.opportunity_id.duplicated().sum(), (~rows.opportunity_id.isin(ids)).sum()
    missing = set() if partial else ids - set(rows.opportunity_id)  # a --reps/--limit run is partial by design
    if dup or phantom or missing:
        out.append(Finding("output_integrity", "high", "agent", f"{version}: {dup} duplicate, {phantom} phantom and {len(missing)} missing deals",
                           int(dup + phantom + len(missing)), [f"missing e.g. {sorted(missing)[:5]}"] if missing else [],
                           "One deal per context, or reconcile output ids against the CRM before use."))
    rows = rows[rows.opportunity_id.isin(ids)].drop_duplicates("opportunity_id")
    # every number the agent states, recomputed from the CRM
    gap_bad, amt_bad, quote_bad, quote_empty = [], [], [], 0
    for r in rows.itertuples():
        d = co.deal(r.opportunity_id)
        acts = co.activities_for(r.opportunity_id)
        true_gap = days_since_buyer_touch(acts, d.sales_agent)
        if true_gap is not None and int(r.days_since_last_buyer_touch) != true_gap:
            gap_bad.append(f"{r.opportunity_id}: said {int(r.days_since_last_buyer_touch)}d, CRM says {true_gap}d")
        if abs(float(r.amount_usd) - deal_amount(co.products, d)) >= 1:
            amt_bad.append(f"{r.opportunity_id}: said ${float(r.amount_usd):,.0f}, CRM/catalogue ${deal_amount(co.products, d):,.0f}")
        q = _norm(getattr(r, "buyer_quote", "") or "")
        if not q:
            quote_empty += 1
        elif q not in " ".join(_norm(t) for t in acts.text):
            quote_bad.append(f"{r.opportunity_id}: “{str(r.buyer_quote)[:60]}…” not in record")
    if gap_bad:
        out.append(Finding("stated_vs_computed", "high", "agent", f"{version}: days-since-buyer-touch wrong on {len(gap_bad)}/{len(rows)} deals", len(gap_bad), gap_bad,
                           "Compute date arithmetic in code; count only buyer-authored activities."))
    if amt_bad:
        out.append(Finding("stated_vs_computed", "high", "agent", f"{version}: amount wrong on {len(amt_bad)} deals", len(amt_bad), amt_bad, "Look amounts up in code with normalised product names."))
    if quote_bad:
        out.append(Finding("stated_vs_computed", "high", "agent", f"{version}: {len(quote_bad)} cited quotes do not exist in the record", len(quote_bad), quote_bad,
                           "Verify quotes verbatim against the record; drop unverifiable ones."))
    if "pipeline_total_usd" in rows:
        stated = float(rows.groupby(["rep", "batch"]).pipeline_total_usd.first().sum())
        true = pipeline_total(co.products, co.deals[co.deals.opportunity_id.isin(rows.opportunity_id)])
        if abs(stated - true) / true > 0.02:
            out.append(Finding("stated_vs_computed", "high", "agent", f"{version}: stated pipeline ${stated:,.0f} vs computed ${true:,.0f} ({(stated - true) / true:+.0%})", 1,
                               [], "Sum amounts in code; the gap usually equals the deals whose product name failed the catalogue lookup."))
    generic = rows.next_action.isin(GENERIC_ACTIONS).mean()
    if generic > 0.15:
        out.append(Finding("specificity", "medium", "agent", f"{version}: {generic:.0%} of next actions are the generic re-engage", int(generic * len(rows)), [],
                           "Force a choice from a specific action menu; make 'disqualify' a first-class answer."))
    p_ = rows.win_probability.astype(float)
    top = (p_ >= 0.85).mean()
    if top > 0.5 or p_.round(2).nunique() <= 5:
        out.append(Finding("calibration_smell", "medium", "agent",
                           f"{version}: {top:.0%} of deals rated ≥0.85 (historical win rate {BASE_WIN_RATE:.0%}); {p_.round(2).nunique()} distinct probabilities",
                           int(top * len(rows)), [f"mean stated p {p_.mean():.2f}"],
                           "Probabilities that don't discriminate make the ranking 'biggest deal first'. Use a calibrated decision model."))
    if quote_empty:
        out.append(Finding("coverage", "info", "agent", f"{version}: {quote_empty}/{len(rows)} deals cite no buyer quote", quote_empty, [], "Expected for 'no objection' deals; watch that it isn't the model avoiding risk."))
    # evidence validity: every issue's evidence must exist verbatim in the deal's record (field evidence excepted)
    if "issues" in rows:
        bad, total = [], 0
        for r in rows.itertuples():
            acts = co.activities_for(r.opportunity_id)
            record = " ".join(_norm(t) for t in acts.text)
            for i in (r.issues if isinstance(r.issues, list) else []):
                ev = str(i.get("evidence") or "")
                if not ev or "=" in ev or ev.startswith("siblings") or ev.startswith("stage="):
                    continue  # field-based evidence
                total += 1
                if _norm(ev) not in record:
                    bad.append(f"{r.opportunity_id} {i['type']}: “{ev[:60]}”")
        if total:
            sev = "high" if len(bad) / total > 0.05 else ("low" if bad else "info")
            out.append(Finding("evidence_validity", sev, "agent", f"{version}: {len(bad)}/{total} issue quotes are not verbatim in the record", len(bad), bad[:6],
                               "Verify quotes against the record before showing them; drop unverifiable ones."))
    return out


# ----------------------------------------------------------------------------- PRISM
def _prism_get(path: str, **params) -> dict | None:
    host, key, pid = os.getenv("PRISM_HOST"), os.getenv("PRISM_API_KEY"), os.getenv("PRISM_PROJECT_ID")
    if not (host and key and pid):
        return None
    r = httpx.get(f"{host}/api/{path}", params={"project_id": pid, **params}, headers={"X-PRISMtrace-Key": key}, timeout=60)
    return r.json() if r.status_code == 200 else None


def check_prism_guardrails(co: Company, activities: pd.DataFrame, hours: int) -> list[Finding]:
    host, key, pid = os.getenv("PRISM_HOST"), os.getenv("PRISM_API_KEY"), os.getenv("PRISM_PROJECT_ID")
    if not (host and key and pid):
        return [Finding("prism", "info", "instrumentation", "PRISM not configured; skipped")]
    r = httpx.get(f"{host}/api/traces/export", params={"project_id": pid, "limit": 5000}, headers={"X-PRISMtrace-Key": key}, timeout=90)
    if r.status_code != 200:
        return [Finding("prism", "info", "instrumentation", f"PRISM export failed: {r.status_code}")]
    from io import StringIO
    e = pd.read_csv(StringIO(r.text))
    e["ts"] = pd.to_datetime(e.timestamp, utc=True)
    e = e[e.ts >= datetime.now(timezone.utc) - timedelta(hours=hours)]
    flagged = e[e.flagged == True]
    if flagged.empty:
        return [Finding("prism_guardrails", "info", "guardrail", f"No guardrail flags on {len(e)} traces in the last {hours}h")]
    record = " ".join(activities.text.astype(str))
    groups: dict[tuple, list] = defaultdict(list)
    for tid in flagged.trace_id.head(60):
        d = _prism_get(f"traces/{tid}")
        for f in (d or {}).get("guardrail_flags") or []:
            m = (f.get("matched_text") or "").split(": ", 1)[-1].strip()
            where = "in the CRM notes the agent was given" if m and m in record else (
                "in the agent's output only" if m and m in str((d or {}).get("output_message", "")) else "not found in current data (stale trace, or already fixed)")
            fp = bool(re.fullmatch(r"Q[1-4]|bypass|[A-Za-z]{1,3}", m or ""))
            agent = (d or {}).get("agent_name") or ((d or {}).get("metadata") or {}).get("agent_name") or "?"
            groups[(f.get("rule_name"), where, fp)].append(f"{agent} {tid[:8]}: {m!r}")
    out = []
    for (rule, where, fp), ev in groups.items():
        sev = "low" if fp else ("high" if "CRM notes" in where else "medium")
        src = "guardrail" if fp else ("data" if "CRM notes" in where else "agent")
        out.append(Finding("prism_guardrails", sev, src, f"PRISM {rule}: {len(ev)} traces, matched text is {where}" + (" — looks like a keyword false positive" if fp else ""),
                           len(ev), ev, "Tune the guardrail pattern." if fp else ("Clean the source data / generation step." if src == "data" else "Redact or constrain the agent's output.")))
    return out


def check_reviews() -> list[Finding]:
    """Manager reviews are the only ground truth on customer data: flag types the manager keeps rejecting."""
    from .score_issues import observed_precision
    out = []
    for t, r in observed_precision().items():
        if r["reviewed"] >= 10 and r["hi"] < 0.7:
            out.append(Finding("reviews", "high", "agent", f"{t}: observed precision {r['precision']:.0%} on {r['reviewed']} reviews (95% ≤ {r['hi']:.0%})",
                               r["reviewed"], [], "Disable this check for this company (ledger.json disabled_checks) or fix its comparison rule."))
    return out


def check_prism_rules(hours: int, sample: int = 60) -> list[Finding]:
    lst = _prism_get("trajectories", limit=500)
    if not lst:
        return [Finding("prism_rules", "info", "instrumentation", "No trajectories readable from PRISM")]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    trajs = [t for t in lst["trajectories"] if pd.Timestamp(t["created_at"]).tz_convert("UTC") >= cutoff]
    fails: dict[tuple, list] = defaultdict(list)
    seen = Counter()
    for t in trajs[:sample]:
        ev = _prism_get(f"trajectories/{t['id']}/evaluation")
        seen[t["agent_name"]] += 1
        for rule in (ev or {}).get("rules", []):
            if not rule["passed"] and rule["max_score"]:
                fails[(t["agent_name"], rule["rule_id"], rule["rule_name"])].append(f"{t['id'][:8]}: {rule.get('evidence', '')[:80]}")
    out = []
    for (agent, rid, name), ev in fails.items():
        share = len(ev) / max(seen[agent], 1)
        if share < 0.2:
            continue
        out.append(Finding("prism_rules", "medium", "instrumentation", f"{agent}: PRISM rule {rid} “{name}” fails on {share:.0%} of sampled runs", len(ev), ev[:4],
                           {"CORR-001": "Mark the last step step_type=final_answer.", "EFF-001": "Give repeated tool steps distinct tool names or merge them."}.get(rid, "Read the rule evidence.")))
    if not out:
        out.append(Finding("prism_rules", "info", "instrumentation", f"No PRISM rule fails ≥20% across {sum(seen.values())} sampled runs"))
    return out


# ----------------------------------------------------------------------------- run
def run(co: Company, versions=("v1", "v2"), activities_path: str | None = None, hours: int = 24, prism: bool = True,
        partial: bool = False) -> list[Finding]:
    acts = pd.read_csv(activities_path) if activities_path else co.activities
    findings = check_data_hygiene(co, acts) + check_catalogue(co) + check_reviews()
    for v in versions:
        findings += check_output(co, v, partial=partial)
    if prism:
        findings += check_prism_guardrails(co, acts, hours) + check_prism_rules(hours)
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: (order[f.severity], f.source))
    return findings


def report(findings: list[Finding], label: str = "audit") -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    n = Counter(f.severity for f in findings)
    md = [f"# Ledger audit — {ts}", "", f"{n.get('high', 0)} high · {n.get('medium', 0)} medium · {n.get('low', 0)} low · {n.get('info', 0)} info", ""]
    for src in ("data", "agent", "guardrail", "instrumentation"):
        fs = [f for f in findings if f.source == src]
        if fs:
            md += [f"## {src}", ""] + [f.md() for f in fs] + [""]
    Path(ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"{label}.md").write_text("\n".join(md))
    (ROOT / "reports" / f"{label}.json").write_text(json.dumps([asdict(f) for f in findings], indent=1))
    # the audit is itself an agent run: one step per finding, visible in PRISM
    by_check: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_check[f.check].append(f)
    steps = [tracing.step("plan", "checks: " + ", ".join(by_check))]
    for check, fs in by_check.items():
        steps.append(tracing.step(f"check:{check}", "\n".join(f"[{f.severity}/{f.source}] {f.title}" for f in fs), tool=f"audit:{check}",
                                  input_summary=f"{len(fs)} findings", status="error" if any(f.severity == "high" for f in fs) else "success"))
        if any(f.severity == "high" for f in fs):
            steps.append(tracing.step("recovery", "; ".join(f.fix for f in fs if f.severity == "high")[:1500]))
    steps.append(tracing.step("final_answer", f"{len(findings)} findings, {n.get('high', 0)} high → reports/{label}.md"))
    tracing.trajectory(version="audit", session_id=f"audit-{datetime.now():%Y%m%d-%H%M}", steps=steps, model="deterministic",
                       final_status="error" if n.get("high") else "success")
    return "\n".join(md)

"""Score a list of issues against the planted anomaly labels (demo/proof only).

Per-type precision/recall/F1 at the (deal, type) level, overall micro F1, and the
false-positive rate on clean deals — the number a manager feels as "noise".
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .config import COMPANY_DIR
from .rules import Issue

TYPES = ["S1_past_close_date", "S2_no_next_step", "S3_dormant", "S4_amount_blank_late", "S5_stalled_early_stage",
         "S6_duplicate_deal", "S7_activity_before_creation", "S8_last_activity_field_wrong",
         "M1_stage_vs_buyer", "M2_contact_contradiction", "M3_expired_promise", "M4_timeline_contradiction",
         "M5_scope_vs_amount", "M6_zombie", "M7_cross_deal_contact", "M8_happy_ears", "M9_missing_economic_buyer", "M10_arithmetic"]


def load_labels() -> pd.DataFrame:
    return pd.read_csv(COMPANY_DIR / "anomalies.csv")


def score(issues: list[Issue], all_deals: list[str], name: str) -> dict:
    lab = load_labels()
    truth = {(r.opportunity_id, r.type) for r in lab.itertuples()}
    pred = {(i.opportunity_id, i.type) for i in issues}
    per = {}
    for t in TYPES:
        tp = len({k for k in pred if k[1] == t and k in truth})
        fp = len({k for k in pred if k[1] == t and k not in truth})
        fn = len({k for k in truth if k[1] == t and k not in pred})
        p = tp / (tp + fp) if tp + fp else None
        r = tp / (tp + fn) if tp + fn else None
        f = 2 * p * r / (p + r) if p and r else (0.0 if (tp + fn) else None)
        per[t] = dict(tp=tp, fp=fp, fn=fn, precision=p, recall=r, f1=f)
    tp = len(pred & truth); fp = len(pred - truth); fn = len(truth - pred)
    clean = set(all_deals) - set(lab.opportunity_id)
    flagged_clean = {i.opportunity_id for i in issues} & clean
    sem = [t for t in TYPES if t.startswith("M")]; syn = [t for t in TYPES if t.startswith("S")]

    def micro(ts):
        a = sum(per[t]["tp"] for t in ts); b = sum(per[t]["fp"] for t in ts); c = sum(per[t]["fn"] for t in ts)
        return dict(precision=a / (a + b) if a + b else 0, recall=a / (a + c) if a + c else 0)
    return dict(name=name, findings=len(pred), tp=tp, fp=fp, fn=fn,
                precision=tp / (tp + fp) if tp + fp else 0, recall=tp / (tp + fn) if tp + fn else 0,
                syntactic=micro(syn), semantic=micro(sem),
                clean_deals=len(clean), clean_flagged=len(flagged_clean), false_alarm_rate=len(flagged_clean) / len(clean) if clean else 0,
                per_type=per)


def table(scores: list[dict]) -> str:
    names = [s["name"] for s in scores]
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    def row(label, f):
        lines.append(f"| {label} | " + " | ".join(f(s) for s in scores) + " |")
    row("findings", lambda s: str(s["findings"]))
    row("precision / recall (all)", lambda s: f"{s['precision']:.0%} / {s['recall']:.0%}")
    row("syntactic S1–S8 recall", lambda s: f"{s['syntactic']['recall']:.0%}")
    row("semantic M1–M10 recall", lambda s: f"{s['semantic']['recall']:.0%}")
    row("semantic precision", lambda s: f"{s['semantic']['precision']:.0%}")
    row("clean deals falsely flagged", lambda s: f"{s['clean_flagged']}/{s['clean_deals']} ({s['false_alarm_rate']:.0%})")
    lines += ["", "| type | " + " | ".join(f"{n} P/R" for n in names) + " |", "|---|" + "---|" * len(names)]
    for t in TYPES:
        cells = []
        for s in scores:
            p = s["per_type"][t]
            cells.append("—" if p["recall"] is None and p["precision"] is None else f"{(p['precision'] or 0):.0%} / {(p['recall'] or 0):.0%} ({p['tp']}/{p['tp'] + p['fn']})")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    return "\n".join(lines)

"""Plant labelled pipeline anomalies into the demo company. Runs after build_company.py.

Two kinds, mirroring what a rules engine can and cannot see:
  S* syntactic  — visible in CRM fields alone (past close date, no next step, dormant,
                  blank amount, stalled early stage, duplicate deal, impossible dates,
                  last_activity field wrong)
  M* semantic   — only visible by reading the record against the fields (stage contradicts
                  the buyer, contact left, expired promise, timeline/scope/arithmetic
                  contradictions, zombie deal, cross-deal contact, happy ears, missing
                  economic buyer)
Some labels are derived from the outcome story a deal already carries; the rest are injected
here. Near-misses are planted too, so false positives are measurable. Labels go to
data/company/anomalies.csv (hidden from agents). Deterministic.
"""
from __future__ import annotations

import random
import re
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "company"
SNAPSHOT = pd.Timestamp("2026-10-19")
LATE = {"Proposal", "Negotiation"}
rng = random.Random(41)

FIRST = ["Amara", "Bo", "Cyrus", "Dara", "Elif", "Farid", "Gia", "Hiro", "Isla", "Jun", "Kira", "Lior", "Mira", "Nils"]
LAST = ["Volkov", "Achebe", "Lindgren", "Rahimi", "Oyelaran", "Takeda", "Brandt", "Nwosu", "Sorensen", "Valdez"]


def person():
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def main():
    deals = pd.read_csv(D / "deals.csv", parse_dates=["created_date", "expected_close", "last_activity_date"])
    acts = pd.read_csv(D / "activities.csv", parse_dates=["date"])
    contacts = pd.read_csv(D / "contacts.csv")
    truth = pd.read_csv(D / "ground_truth.csv")
    prices = pd.read_csv(D / "products.csv")
    price = {"".join(p.lower().split()): float(v) for p, v in zip(prices["product"], prices.sales_price)}
    arch = truth.set_index("opportunity_id").archetype
    labels: list[dict] = []

    def label(oid, typ, detail):
        labels.append(dict(opportunity_id=oid, type=typ, detail=detail))

    def deal_acts(oid):
        return acts[acts.opportunity_id == oid].sort_values("date")

    def econ(oid):
        c = contacts[(contacts.opportunity_id == oid) & (contacts.role == "economic_buyer")]
        return c.iloc[0]["name"] if len(c) else None

    # ---- derived semantic labels (the story already contains the contradiction) -------
    for oid, a in arch.items():
        row = deals[deals.opportunity_id == oid].iloc[0]
        if a in ("budget_frozen", "competitor_leaning", "competitor_decided", "looked_healthy") and row.stage in LATE:
            label(oid, "M1_stage_vs_buyer", f"stage {row.stage} but buyer said otherwise ({a})")
        if a == "champion_left":
            label(oid, "M2_contact_contradiction", "auto-reply says primary contact left; still primary")
        if a == "competitor_decided":
            label(oid, "M6_zombie", "buyer chose a competitor; deal still open")
        if a in ("looked_healthy", "budget_frozen", "competitor_leaning"):
            label(oid, "M8_happy_ears", "rep note positive after buyer declined/paused")
        if a == "no_authority" and row.stage in LATE:
            label(oid, "M2_contact_contradiction", "primary contact says they don't own the budget/decision; stage is late")
        if a == "looked_healthy":
            label(oid, "M4_timeline_contradiction", "expected_close within weeks; buyer paused vendor onboarding indefinitely")

    # ---- injected: M3 expired promise (buyer promised PO/signature, then silence > 14d) -----
    promise = [oid for oid, a in arch.items() if a in ("clean_run", "noisy_rep", "verbal_yes_then_lost", "price_resolved", "stage_lagging")]
    for oid in rng.sample(promise, min(14, len(promise))):
        da = deal_acts(oid)
        rep = deals.loc[deals.opportunity_id == oid, "sales_agent"].iloc[0]
        buyer_rows = da[(da.author != rep) & (da.author != "system")]
        if buyer_rows.empty:
            continue
        last_b = buyer_rows.index[-1]
        shift = timedelta(days=rng.randint(18, 30)) - (SNAPSHOT - acts.loc[last_b, "date"])
        if shift.days <= 0:
            continue
        created = deals.loc[deals.opportunity_id == oid, "created_date"].iloc[0]
        idx = da.index[da.index <= last_b]
        if acts.loc[idx, "date"].min() - shift < created:
            deals.loc[deals.opportunity_id == oid, "created_date"] = acts.loc[idx, "date"].min() - shift - timedelta(days=2)
        acts.loc[idx, "date"] = acts.loc[idx, "date"] - shift
        acts.loc[[i for i in da.index if i > last_b], "date"] = [SNAPSHOT - timedelta(days=rng.randint(1, 6)) for _ in range(sum(i > last_b for i in da.index))]
        label(oid, "M3_expired_promise", f"buyer promised PO/signature {(SNAPSHOT - acts.loc[last_b, 'date']).days}d ago, nothing since")

    # ---- injected: M4 timeline contradiction ------------------------------------------
    for oid, a in arch.items():
        if a == "evaluating_open_lost":  # buyer: "decision in about three weeks"
            da = deal_acts(oid)
            said = da[da.text.str.contains("three weeks", case=False)]
            if said.empty:
                continue
            decision = said.date.iloc[0] + timedelta(days=21)
            if rng.random() < 0.6:
                deals.loc[deals.opportunity_id == oid, "expected_close"] = decision - timedelta(days=rng.randint(7, 14))
                label(oid, "M4_timeline_contradiction", "expected_close before the buyer's stated decision date")
            else:  # near-miss: consistent
                deals.loc[deals.opportunity_id == oid, "expected_close"] = decision + timedelta(days=rng.randint(3, 10))
        if a == "budget_frozen":  # buyer: capex frozen until next fiscal year
            deals.loc[deals.opportunity_id == oid, "expected_close"] = SNAPSHOT + timedelta(days=rng.randint(10, 40))
            label(oid, "M4_timeline_contradiction", "expected_close this quarter; buyer said no budget until next fiscal year")

    # ---- injected: M5 scope / M10 arithmetic (buyer talks about units; amount is one unit) ---
    scope_pool = [oid for oid, a in arch.items() if a in ("bakeoff_won", "quiet_late_stage", "reopened_then_closed", "stage_lagging")]
    for oid in rng.sample(scope_pool, min(16, len(scope_pool))):
        row = deals[deals.opportunity_id == oid].iloc[0]
        p = price["".join(row["product"].lower().split())]
        units = rng.choice([2, 3, 4])
        rep = row.sales_agent
        champ = row.primary_contact
        da = deal_acts(oid)
        kind = rng.choice(["M5", "M10", "near"])
        if kind == "M10":
            stated = units * p * rng.choice([0.8, 1.25, 1.5])
            text = f"To confirm scope: {units} units of {row['product']} at list, so ${stated:,.0f} total. Please quote that."
            label(oid, "M10_arithmetic", f"buyer says {units}×${p:,.0f} = ${stated:,.0f}; correct is ${units * p:,.0f}")
        else:
            text = f"To confirm scope: we'd take {units} units of {row['product']} at list, ${units * p:,.0f} total."
            if kind == "M5":
                label(oid, "M5_scope_vs_amount", f"buyer scope {units} units (${units * p:,.0f}); CRM amount is one unit")
            else:  # near-miss: CRM amount matches the stated scope
                deals.loc[deals.opportunity_id == oid, "amount"] = units * p
        date = min(da.date.max() + timedelta(days=1), SNAPSHOT)
        acts.loc[len(acts)] = dict(activity_id=f"{oid}-{len(da) + 1}", opportunity_id=oid, date=date, type="email", author=champ, text=text)

    # ---- injected: M2b economic buyer in CRM ≠ named in notes; M9 missing economic buyer ---
    late = deals[deals.stage.isin(LATE)].opportunity_id.tolist()
    rng.shuffle(late)
    m2b, m9 = late[:12], late[12:32]
    for oid in m2b:
        e = econ(oid)
        if e and acts[(acts.opportunity_id == oid) & acts.text.str.contains(re.escape(e))].shape[0]:
            contacts.loc[(contacts.opportunity_id == oid) & (contacts.role == "economic_buyer"), "name"] = person()
            label(oid, "M2_contact_contradiction", f"CRM economic buyer differs from the one named in the notes ({e})")
    for oid in m9:
        if econ(oid):
            contacts = contacts[~((contacts.opportunity_id == oid) & (contacts.role == "economic_buyer"))]
            named = acts[(acts.opportunity_id == oid) & acts.text.str.contains("approved|signed off|froze|budget", case=False)].shape[0]
            label(oid, "M9_missing_economic_buyer", "late stage, no economic buyer in CRM" + (" (one is named in the notes)" if named else ""))

    # ---- injected: M7 cross-deal — contact left on deal A; deal B at same account still lists them ---
    multi = deals.groupby("account").opportunity_id.apply(list)
    multi = [ids for ids in multi if len(ids) >= 2]
    rng.shuffle(multi)
    used = set()
    for ids in multi[:8]:
        a_id, b_id = rng.sample(ids, 2)
        if a_id in used or b_id in used:
            continue
        a_row = deals[deals.opportunity_id == a_id].iloc[0]
        champ = a_row.primary_contact
        account = a_row.account
        e = econ(a_id) or person()
        da = deal_acts(a_id)
        date = min(da.date.max() + timedelta(days=rng.randint(1, 3)), SNAPSHOT - timedelta(days=1))
        acts.loc[len(acts)] = dict(activity_id=f"{a_id}-{len(da) + 1}", opportunity_id=a_id, date=date, type="email", author="system",
                                   text=f"Auto-reply: {champ} is no longer with {account}. For infrastructure enquiries please contact {e}.")
        deals.loc[deals.opportunity_id == b_id, "primary_contact"] = champ
        contacts.loc[(contacts.opportunity_id == b_id) & (contacts.role == "champion"), "name"] = champ
        label(a_id, "M2_contact_contradiction", "auto-reply says primary contact left; still primary")
        label(b_id, "M7_cross_deal_contact", f"primary contact {champ} left {account} per auto-reply on deal {a_id}")
        used |= {a_id, b_id}

    # ---- injected syntactic ------------------------------------------------------------
    open_ids = deals.opportunity_id.tolist()
    for oid in rng.sample(open_ids, 12):  # S1 close date in the past
        deals.loc[deals.opportunity_id == oid, "expected_close"] = SNAPSHOT - timedelta(days=rng.randint(3, 40))
        label(oid, "S1_past_close_date", "expected_close is before today")
    for oid in rng.sample(open_ids, 8):  # S7 activity dated before deal creation
        da = deal_acts(oid)
        first = da.index[0]
        acts.loc[first, "date"] = deals.loc[deals.opportunity_id == oid, "created_date"].iloc[0] - timedelta(days=rng.randint(3, 20))
        label(oid, "S7_activity_before_creation", "an activity is dated before the deal was created")
    for oid in rng.sample(open_ids, 8):  # S8 last_activity_date field wrong
        deals.loc[deals.opportunity_id == oid, "last_activity_date"] = deal_acts(oid).date.max() - timedelta(days=rng.randint(10, 30))
        label(oid, "S8_last_activity_field_wrong", "last_activity_date field is older than the newest activity")
    for oid in rng.sample([o for o in open_ids if o not in used], 7):  # S6 duplicate open deal
        row = deals[deals.opportunity_id == oid].iloc[0].copy()
        new_id = f"{oid[:6]}DP"
        row["opportunity_id"] = new_id
        row["created_date"] = row.created_date + timedelta(days=rng.randint(1, 5))
        row["stage"] = rng.choice(["Prospecting", "Qualification"])
        row["next_step"] = ""
        row["last_activity_date"] = row.created_date
        deals = pd.concat([deals, row.to_frame().T], ignore_index=True)
        contacts = pd.concat([contacts, contacts[contacts.opportunity_id == oid].assign(opportunity_id=new_id)], ignore_index=True)
        acts.loc[len(acts)] = dict(activity_id=f"{new_id}-1", opportunity_id=new_id, date=row.created_date, type="call", author=row.sales_agent,
                                   text=f"Intro call with {row.primary_contact} about {row['product']}.")
        label(new_id, "S6_duplicate_deal", f"same account+product as {oid}, created days later")
    for oid in rng.sample([o for o in open_ids if o not in used], 6):  # S5 stalled early stage
        deals.loc[deals.opportunity_id == oid, "created_date"] = SNAPSHOT - timedelta(days=rng.randint(120, 160))
        deals.loc[deals.opportunity_id == oid, "stage"] = "Qualification"
        label(oid, "S5_stalled_early_stage", "in Qualification for >2× the median cycle")

    # ---- thin the base generator's random blanks so S2/S4 stay signal, not noise ----------
    late_mask = deals.stage.isin(LATE | {"Discovery"})
    blank_amt = deals.index[late_mask & (deals.amount.isna() | (deals.amount.astype(str).str.strip() == ""))].tolist()
    for i in rng.sample(blank_amt, max(len(blank_amt) - 10, 0)):
        deals.loc[i, "amount"] = price["".join(str(deals.loc[i, "product"]).lower().split())]
    blank_ns = deals.index[late_mask & (deals.next_step.isna() | (deals.next_step.astype(str).str.strip() == ""))].tolist()
    for i in rng.sample(blank_ns, max(len(blank_ns) - 10, 0)):
        deals.loc[i, "next_step"] = rng.choice(["Send proposal", "Confirm PO timing", "Schedule exec call", "Follow up on redlines"])

    # ---- derived syntactic (whatever the data now says) ---------------------------------
    deals["created_date"] = pd.to_datetime(deals.created_date); deals["expected_close"] = pd.to_datetime(deals.expected_close)
    deals["last_activity_date"] = pd.to_datetime(deals.last_activity_date); acts["date"] = pd.to_datetime(acts.date)
    have = {(l["opportunity_id"], l["type"]) for l in labels}
    for r in deals.itertuples():
        da = deal_acts(r.opportunity_id)
        if r.stage in LATE | {"Discovery"} and (pd.isna(r.next_step) or str(r.next_step).strip() == "") and (r.opportunity_id, "S2_no_next_step") not in have:
            label(r.opportunity_id, "S2_no_next_step", "no next step recorded past Qualification")
        if len(da) and (SNAPSHOT - da.date.max()).days > 30 and (r.opportunity_id, "S3_dormant") not in have:
            label(r.opportunity_id, "S3_dormant", f"no activity for {(SNAPSHOT - da.date.max()).days} days")
        if r.stage in LATE and (pd.isna(r.amount) or r.amount == "") and (r.opportunity_id, "S4_amount_blank_late") not in have:
            label(r.opportunity_id, "S4_amount_blank_late", "amount blank past Qualification")

    # ---- derived M3: a buyer promise/callback older than 14 days with no buyer message since -----
    promise_arch = {"clean_run", "noisy_rep", "verbal_yes_then_lost", "price_resolved", "stage_lagging", "quiet_late_stage", "silent_then_signed", "no_authority"}
    have = {(l["opportunity_id"], l["type"]) for l in labels}
    for r in deals.itertuples():
        if arch.get(r.opportunity_id) in promise_arch and (r.opportunity_id, "M3_expired_promise") not in have:
            da = deal_acts(r.opportunity_id)
            b = da[(da.author != r.sales_agent) & (da.author != "system")]
            if len(b) and (SNAPSHOT - b.date.max()).days > 14:
                label(r.opportunity_id, "M3_expired_promise", f"buyer's last promise/callback is {(SNAPSHOT - b.date.max()).days}d old, nothing since")

    # ---- write ---------------------------------------------------------------------------
    deals.sort_values("opportunity_id").to_csv(D / "deals.csv", index=False, date_format="%Y-%m-%d")
    acts.sort_values(["opportunity_id", "date"]).to_csv(D / "activities.csv", index=False, date_format="%Y-%m-%d")
    contacts.to_csv(D / "contacts.csv", index=False)
    lab = pd.DataFrame(labels).drop_duplicates()
    lab.to_csv(D / "anomalies.csv", index=False)
    # ground truth: recompute buyer-touch gap after mutations; duplicates inherit their source's outcome row for eval purposes
    t = truth.set_index("opportunity_id")
    gaps = {}
    for r in deals.itertuples():
        da = deal_acts(r.opportunity_id)
        b = da[(da.author != r.sales_agent) & (da.author != "system")]
        gaps[r.opportunity_id] = int((SNAPSHOT - b.date.max()).days) if len(b) else None
    for l in labels:
        if l["type"] == "S6_duplicate_deal":
            src = l["detail"].split(" as ")[1].split(",")[0]
            t.loc[l["opportunity_id"]] = t.loc[src]
            t.loc[l["opportunity_id"], "outcome"] = "Lost"; t.loc[l["opportunity_id"], "actual_close_value"] = 0.0
            t.loc[l["opportunity_id"], "archetype"] = "duplicate"
    t["days_since_buyer_touch"] = pd.Series(gaps)
    t.reset_index().to_csv(D / "ground_truth.csv", index=False)
    print(f"{len(deals)} deals ({len(deals) - len(truth)} duplicates added), {len(acts)} activities")
    print(lab.type.value_counts().to_string())
    print(f"deals with ≥1 anomaly: {lab.opportunity_id.nunique()} / {len(deals)}  ({lab.opportunity_id.nunique() / len(deals):.0%})")


if __name__ == "__main__":
    main()

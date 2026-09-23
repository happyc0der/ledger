"""Add derived anomaly labels to an existing planted dataset without re-planting.
Used when the definition of a label changes after a (paid) agent run was made on the data."""
import pandas as pd
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "data" / "company"
SNAPSHOT = pd.Timestamp("2026-10-19"); LATE = {"Proposal", "Negotiation"}
deals = pd.read_csv(D / "deals.csv", parse_dates=["created_date"]); acts = pd.read_csv(D / "activities.csv", parse_dates=["date"])
truth = pd.read_csv(D / "ground_truth.csv").set_index("opportunity_id"); lab = pd.read_csv(D / "anomalies.csv")
have = {(r.opportunity_id, r.type) for r in lab.itertuples()}; new = []
promise_arch = {"clean_run", "noisy_rep", "verbal_yes_then_lost", "price_resolved", "stage_lagging", "quiet_late_stage", "silent_then_signed", "no_authority"}
for r in deals.itertuples():
    oid = r.opportunity_id
    if oid not in truth.index: continue
    a = truth.loc[oid].archetype
    if a == "no_authority" and r.stage in LATE and (oid, "M2_contact_contradiction") not in have:
        new.append(dict(opportunity_id=oid, type="M2_contact_contradiction", detail="primary contact says they don't own the budget/decision; stage is late"))
    if a == "looked_healthy" and (oid, "M4_timeline_contradiction") not in have:
        new.append(dict(opportunity_id=oid, type="M4_timeline_contradiction", detail="expected_close within weeks; buyer paused vendor onboarding indefinitely"))
    if a in promise_arch and (oid, "M3_expired_promise") not in have:
        da = acts[acts.opportunity_id == oid]; b = da[(da.author != r.sales_agent) & (da.author != "system")]
        if len(b) and (SNAPSHOT - b.date.max()).days > 14:
            new.append(dict(opportunity_id=oid, type="M3_expired_promise", detail=f"buyer's last promise/callback is {(SNAPSHOT - b.date.max()).days}d old, nothing since"))
lab = pd.concat([lab, pd.DataFrame(new)], ignore_index=True).drop_duplicates()
lab.to_csv(D / "anomalies.csv", index=False)
print(f"added {len(new)} labels; deals with >=1 anomaly: {lab.opportunity_id.nunique()}/{len(deals)}")

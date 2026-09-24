"""Turn a CRM export into Ledger's canonical files.

Ledger reads five CSVs (deals, activities, contacts, products, team) with fixed column
names. Real CRMs export different names, so this maps them: built-in presets for HubSpot
and Salesforce exports, or an explicit JSON mapping for anything else. Stages are mapped
onto Ledger's five canonical stages. Anything unmapped is left blank and the rules engine
will say so (blank amount, no next step) rather than guessing.

    scripts/ingest.py --preset hubspot --deals deals.csv --activities engagements.csv \\
        [--contacts contacts.csv] [--products products.csv] --out data/acme
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

CANON = {
    "deals": ["opportunity_id", "account", "product", "sales_agent", "stage", "amount", "created_date",
              "expected_close", "primary_contact", "last_activity_date", "next_step"],
    "activities": ["activity_id", "opportunity_id", "date", "type", "author", "text", "direction", "from_addr", "to_addr"],
    "contacts": ["opportunity_id", "name", "title", "role", "email"],
    "products": ["product", "series", "sales_price"],
    "team": ["sales_agent", "manager", "regional_office"],
}
STAGES = ["Prospecting", "Qualification", "Discovery", "Proposal", "Negotiation"]

# Column candidates per canonical field (first match wins; case-insensitive, punctuation-insensitive).
PRESETS = {
    "hubspot": {
        "deals": {"opportunity_id": ["Record ID", "Deal ID", "hs_object_id"], "account": ["Associated Company", "Company name", "Associated Company Name"],
                  "product": ["Product", "Line item", "Deal Type", "Deal Name"], "sales_agent": ["Deal owner", "Deal Owner", "Owner"],
                  "stage": ["Deal Stage", "dealstage"], "amount": ["Amount", "amount"], "created_date": ["Create Date", "createdate"],
                  "expected_close": ["Close Date", "closedate"], "primary_contact": ["Associated Contact", "Primary contact", "Contact name"],
                  "last_activity_date": ["Last Activity Date", "notes_last_updated", "Last Contacted"], "next_step": ["Next step", "Next Step", "hs_next_step"]},
        "activities": {"activity_id": ["Record ID", "Engagement ID", "Activity ID"], "opportunity_id": ["Associated Deal", "Deal ID", "Associated Deal IDs"],
                       "date": ["Activity date", "Create Date", "Timestamp", "Date"], "type": ["Activity type", "Type", "Engagement type"],
                       "author": ["Activity assigned to", "Created by", "Owner", "From"], "text": ["Body", "Note body", "Activity body", "Description", "Subject"],
                       "direction": ["Email direction", "hs_email_direction", "Call direction", "hs_call_direction", "Direction"],
                       "from_addr": ["From address", "hs_email_from_email", "From email", "Sender"], "to_addr": ["To address", "hs_email_to_email", "To email", "Recipient"]},
        "contacts": {"opportunity_id": ["Associated Deal", "Deal ID"], "name": ["Name", "Contact name", "Full name"], "title": ["Job Title", "Title"], "role": ["Buying Role", "Role"],
                     "email": ["Email", "Email address"]},
        "stages": {"appointmentscheduled": "Prospecting", "qualifiedtobuy": "Qualification", "presentationscheduled": "Discovery",
                   "decisionmakerboughtin": "Proposal", "contractsent": "Negotiation"},
        "roles": {"decision maker": "economic_buyer", "budget holder": "economic_buyer", "executive sponsor": "economic_buyer",
                  "champion": "champion", "influencer": "champion", "end user": "champion"},
    },
    "salesforce": {
        "deals": {"opportunity_id": ["Opportunity ID", "Id", "OPPORTUNITY_ID"], "account": ["Account Name", "AccountName", "Account"],
                  "product": ["Product", "Primary Product", "Opportunity Name", "Name"], "sales_agent": ["Opportunity Owner", "Owner", "OwnerName"],
                  "stage": ["Stage", "StageName"], "amount": ["Amount"], "created_date": ["Created Date", "CreatedDate"],
                  "expected_close": ["Close Date", "CloseDate"], "primary_contact": ["Primary Contact", "Contact Name", "ContactName"],
                  "last_activity_date": ["Last Activity", "LastActivityDate"], "next_step": ["Next Step", "NextStep"]},
        "activities": {"activity_id": ["Activity ID", "Id", "Task ID"], "opportunity_id": ["Related To ID", "WhatId", "Opportunity ID"],
                       "date": ["Date", "ActivityDate", "Due Date"], "type": ["Type", "TaskSubtype", "Subject"],
                       "author": ["Assigned", "Owner", "Assigned To", "CreatedBy"], "text": ["Comments", "Description", "Subject", "TextBody"],
                       "direction": ["Incoming", "Direction", "Call Type"], "from_addr": ["From Address", "FromAddress"], "to_addr": ["To Address", "ToAddress"]},
        "contacts": {"opportunity_id": ["Opportunity ID", "OpportunityId"], "name": ["Contact Name", "Name"], "title": ["Title"], "role": ["Role", "Contact Role"],
                     "email": ["Email"]},
        "stages": {"prospecting": "Prospecting", "qualification": "Qualification", "needs analysis": "Discovery", "value proposition": "Discovery",
                   "id. decision makers": "Discovery", "perception analysis": "Proposal", "proposal/price quote": "Proposal", "negotiation/review": "Negotiation"},
        "roles": {"economic buyer": "economic_buyer", "economic decision maker": "economic_buyer", "executive sponsor": "economic_buyer",
                  "business user": "champion", "technical buyer": "champion", "evaluator": "champion", "champion": "champion"},
    },
    "ledger": {"deals": {}, "activities": {}, "contacts": {}, "stages": {}, "roles": {}},  # already canonical
}


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _map(df: pd.DataFrame, spec: dict[str, list[str]], canon: list[str]) -> tuple[pd.DataFrame, dict]:
    cols = {_key(c): c for c in df.columns}
    out, used = pd.DataFrame(index=df.index), {}
    for field in canon:
        src = None
        if _key(field) in cols:
            src = cols[_key(field)]
        else:
            for cand in spec.get(field, []):
                if _key(cand) in cols:
                    src = cols[_key(cand)]
                    break
        out[field] = df[src] if src is not None else None
        used[field] = src
    return out, used


CLOSED = re.compile(r"closed|won|lost|dead|disqualif|churn", re.I)


def _stage(v, table: dict) -> str | None:
    """Canonical stage, or None when the value is a custom stage we don't recognise (kept, not dropped)."""
    k = str(v).strip().lower()
    if k in table:
        return table[k]
    for s in STAGES:  # already canonical, any case
        if k == s.lower():
            return s
    for pat, s in [("prospect", "Prospecting"), ("qualif", "Qualification"), ("discover", "Discovery"), ("demo", "Discovery"),
                   ("proposal", "Proposal"), ("quote", "Proposal"), ("negotiat", "Negotiation"), ("contract", "Negotiation"), ("verbal", "Negotiation")]:
        if pat in k:
            return s
    return None


def _is_closed(v) -> bool:
    return bool(CLOSED.search(str(v)))


def ingest(preset: str, out: Path, *, deals: Path, activities: Path | None = None, contacts: Path | None = None,
           products: Path | None = None, team: Path | None = None, mapping: dict | None = None, company: str = "Your company",
           allow_no_buyer: bool = False) -> dict:
    spec = json.loads(json.dumps(PRESETS[preset]))
    for k, v in (mapping or {}).items():  # explicit overrides: {"deals": {"amount": ["Deal Value"]}, "stages": {...}}
        spec[k] = {**spec.get(k, {}), **v}
    out.mkdir(parents=True, exist_ok=True)
    report = {}

    d_raw = pd.read_csv(deals)
    d, used = _map(d_raw, spec["deals"], CANON["deals"])
    d["stage_raw"] = d.stage
    d["stage"] = d.stage_raw.map(lambda v: _stage(v, spec["stages"]))
    for c in ("created_date", "expected_close", "last_activity_date"):
        d[c] = pd.to_datetime(d[c], errors="coerce").dt.date
    d["amount"] = pd.to_numeric(d.amount.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
    d["opportunity_id"] = d.opportunity_id.astype(str)
    closed = d.stage_raw.map(_is_closed)
    # history and a per-company profile come from the closed deals, before they are dropped
    hist = d[closed].copy()
    hist["outcome"] = hist.stage_raw.map(lambda v: "Won" if re.search(r"won", str(v), re.I) else "Lost")
    hist.to_csv(out / "history.csv", index=False)
    profile = {"n_closed": int(len(hist)), "source": "learned" if len(hist) >= 30 else "default"}
    if len(hist) >= 30:
        won = hist[hist.outcome == "Won"]
        profile["base_win_rate"] = round(float((hist.outcome == "Won").mean()), 3)
        cyc = (pd.to_datetime(won.expected_close) - pd.to_datetime(won.created_date)).dt.days.dropna()
        if len(cyc):
            profile["median_cycle_days"] = int(cyc.median())
    unmapped = d[~closed & d.stage.isna()].stage_raw.value_counts().to_dict()
    report["deals"] = {"rows": len(d), "dropped_closed": int(closed.sum()), "kept_unmapped_stage": {str(k): int(v) for k, v in unmapped.items()},
                       "mapping_hint": {"stages": {str(k): "Proposal|Negotiation|..." for k in unmapped}} if unmapped else None, "columns": used}
    d = d[~closed].copy()
    d.to_csv(out / "deals.csv", index=False)

    if activities:
        a_raw = pd.read_csv(activities)
        a, used = _map(a_raw, spec["activities"], CANON["activities"])
        a["date"] = pd.to_datetime(a.date, errors="coerce").dt.date
        a["type"] = a.type.astype(str).str.lower().map(lambda t: "email" if "mail" in t else ("meeting" if "meet" in t else ("call" if "call" in t else "note")))
        a["opportunity_id"] = a.opportunity_id.astype(str).str.split(";").str[0].str.strip()
        a = a[a.opportunity_id.isin(d.opportunity_id) & a.text.notna()]
        if a.activity_id.isna().all():
            a["activity_id"] = [f"{o}-{i}" for i, o in enumerate(a.opportunity_id, 1)]
        report["activities"] = {"rows": len(a), "columns": used}
        if len(a):  # attribution coverage: how much of the record can carry buyer evidence
            from .attribution import annotate
            team_df = pd.read_csv(team) if team else pd.DataFrame({"sales_agent": d.sales_agent.dropna().unique(), "manager": ""})
            cts = pd.read_csv(contacts) if contacts else pd.DataFrame(columns=["opportunity_id", "name"])
            cts_c, _ = _map(cts, spec["contacts"], CANON["contacts"]) if contacts else (pd.DataFrame(columns=CANON["contacts"]), {})
            cts_c["opportunity_id"] = cts_c.opportunity_id.astype(str)
            ann = annotate(a.assign(date=a.date.astype(str)), d, cts_c, team_df)
            counts = ann.speaker.value_counts().to_dict()
            report["attribution"] = {k: int(v) for k, v in counts.items()}
            if counts.get("buyer", 0) == 0 and not allow_no_buyer:
                raise SystemExit("No activity could be attributed to a buyer (every row reads as the rep). Ledger would find nothing and "
                                 "say nothing. Provide email direction / from-address columns (see PRESETS) or a contacts file with names, "
                                 "or pass allow_no_buyer=True to proceed with rules only.")
    else:
        a = pd.DataFrame(columns=CANON["activities"])
        report["activities"] = {"rows": 0, "note": "no activities file: only rules will run; the claim ledger needs notes"}
    a.to_csv(out / "activities.csv", index=False)

    if contacts:
        c_raw = pd.read_csv(contacts)
        c, used = _map(c_raw, spec["contacts"], CANON["contacts"])
        c["role"] = c.role.astype(str).str.strip().str.lower().map(lambda r: spec["roles"].get(r, "economic_buyer" if any(x in r for x in ("econ", "decision", "budget", "sponsor")) else "champion"))
        c["opportunity_id"] = c.opportunity_id.astype(str)
        c = c[c.opportunity_id.isin(d.opportunity_id)]
        report["contacts"] = {"rows": len(c), "columns": used}
    else:  # derive the champion from the deal's primary contact; economic buyer unknown
        c = d[["opportunity_id", "primary_contact"]].rename(columns={"primary_contact": "name"}).assign(title="", role="champion")
        report["contacts"] = {"rows": len(c), "note": "derived from primary_contact; no economic buyers known"}
    c.to_csv(out / "contacts.csv", index=False)

    if products:
        pd.read_csv(products).to_csv(out / "products.csv", index=False)
    else:  # no catalogue: amounts must come from the deal; scope/arithmetic checks are skipped
        pd.DataFrame(columns=CANON["products"]).to_csv(out / "products.csv", index=False)
        report["products"] = {"note": "no catalogue: list-price lookups disabled"}
    if team:
        pd.read_csv(team).to_csv(out / "team.csv", index=False)
    else:
        pd.DataFrame({"sales_agent": sorted(d.sales_agent.dropna().unique()), "manager": "", "regional_office": ""}).to_csv(out / "team.csv", index=False)
    pd.DataFrame(columns=["account", "sector", "year_established", "revenue", "employees", "office_location", "subsidiary_of"]).to_csv(out / "accounts.csv", index=False)
    (out / "company.md").write_text(f"# {company} — pipeline review brief\n\nImported from a {preset} export. {len(d)} open opportunities, "
                                    f"{d.sales_agent.nunique()} reps.\n")
    (out / "profile.json").write_text(json.dumps(profile, indent=1))
    (out / "ingest_report.json").write_text(json.dumps(report, indent=1, default=str))
    return report

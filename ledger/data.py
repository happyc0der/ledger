"""Load the demo company. Ground truth is loaded by a separate function that agents never call."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .config import COMPANY_DIR


@dataclass
class Company:
    brief: str
    deals: pd.DataFrame        # agent-visible snapshot, one row per open opportunity
    activities: pd.DataFrame   # call notes / emails / meetings
    contacts: pd.DataFrame
    products: pd.DataFrame     # catalogue with list prices (spelling differs from pipeline!)
    team: pd.DataFrame
    accounts: pd.DataFrame
    _acts_by_deal: dict = field(default_factory=dict, repr=False)

    def reps(self) -> list[str]:
        return sorted(self.deals.sales_agent.unique())

    def deals_for(self, rep: str) -> pd.DataFrame:
        return self.deals[self.deals.sales_agent == rep]

    def activities_for(self, opportunity_id: str) -> pd.DataFrame:
        if not self._acts_by_deal:
            self._acts_by_deal = {k: g.sort_values("date") for k, g in self.activities.groupby("opportunity_id")}
        return self._acts_by_deal.get(opportunity_id, self.activities.iloc[0:0])

    def deal(self, opportunity_id: str) -> pd.Series:
        return self.deals.set_index("opportunity_id").loc[opportunity_id]


def load_company() -> Company:
    from .attribution import annotate
    d = COMPANY_DIR
    co = Company(
        brief=(d / "company.md").read_text(),
        deals=pd.read_csv(d / "deals.csv", parse_dates=["created_date", "expected_close", "last_activity_date"], dtype={"opportunity_id": str}),
        activities=pd.read_csv(d / "activities.csv", parse_dates=["date"], dtype={"opportunity_id": str, "activity_id": str}),
        contacts=pd.read_csv(d / "contacts.csv", dtype={"opportunity_id": str}),
        products=pd.read_csv(d / "products.csv"),
        team=pd.read_csv(d / "team.csv"),
        accounts=pd.read_csv(d / "accounts.csv") if (d / "accounts.csv").exists() else pd.DataFrame(columns=["account"]),
    )
    co.activities = annotate(co.activities, co.deals, co.contacts, co.team)
    return co


def load_truth() -> pd.DataFrame:
    """Hidden outcomes. Only evaluate.py may import this."""
    return pd.read_csv(COMPANY_DIR / "ground_truth.csv", parse_dates=["actual_close_date"]).set_index("opportunity_id")

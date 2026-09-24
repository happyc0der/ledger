import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ledger.attribution import annotate  # noqa: E402
from ledger.data import Company  # noqa: E402

AS_OF = pd.Timestamp("2026-10-19")


def make_company(deals, activities, contacts=None, products=None, team=None) -> Company:
    deals = pd.DataFrame(deals)
    for c in ("created_date", "expected_close", "last_activity_date"):
        if c in deals:
            deals[c] = pd.to_datetime(deals[c])
    acts = pd.DataFrame(activities, columns=["activity_id", "opportunity_id", "date", "type", "author", "text"])
    if len(acts):
        acts["date"] = pd.to_datetime(acts["date"])
    contacts = pd.DataFrame(contacts or [], columns=["opportunity_id", "name", "title", "role"])
    products = pd.DataFrame(products or [{"product": "GTX Basic", "series": "GTX", "sales_price": 550}])
    team = pd.DataFrame(team or [{"sales_agent": a, "manager": "M", "regional_office": "C"} for a in deals.sales_agent.unique()])
    co = Company(brief="# Test", deals=deals, activities=acts, contacts=contacts, products=products, team=team,
                 accounts=pd.DataFrame(columns=["account"]))
    co.activities = annotate(co.activities, co.deals, co.contacts, co.team)
    return co


@pytest.fixture
def one_deal():
    return dict(opportunity_id="D1", account="Acme", product="GTX Basic", sales_agent="Rep One", stage="Negotiation", amount=550.0,
                created_date="2026-08-01", expected_close="2026-11-15", primary_contact="Priya Okafor",
                last_activity_date="2026-10-10", next_step="Send proposal")

"""Deterministic helpers. v2 calls these instead of letting the model do arithmetic;
the evaluator uses them to compute the truth every cited number is checked against."""
from __future__ import annotations

import pandas as pd

from .config import SNAPSHOT


def normalize_product(name: str) -> str:
    return "".join(name.lower().split())


def price_table(products: pd.DataFrame) -> dict[str, float]:
    return {normalize_product(r.product): float(r.sales_price) for r in products.itertuples()}


def list_price(products: pd.DataFrame, product: str) -> float | None:
    """Catalogue price, or None when there is no catalogue / no such product."""
    return price_table(products).get(normalize_product(str(product)))


def deal_amount(products: pd.DataFrame, deal: pd.Series) -> float:
    """CRM amount if the rep entered one, else catalogue list price, else 0 (and a rule will flag it)."""
    amt = deal.get("amount")
    if pd.notna(amt) and amt != "":
        return float(amt)
    return list_price(products, deal["product"]) or 0.0


def pipeline_total(products: pd.DataFrame, deals: pd.DataFrame) -> float:
    return float(sum(deal_amount(products, d) for _, d in deals.iterrows()))


def days_since_buyer_touch(activities: pd.DataFrame, rep: str, snapshot: pd.Timestamp = SNAPSHOT) -> int | None:
    """Days since the BUYER last did something. Rep voicemails and system auto-replies don't count."""
    if "speaker" in activities.columns:
        buyer = activities[activities.speaker == "buyer"]
    else:
        buyer = activities[(activities.author != rep) & (activities.author != "system")]
    if buyer.empty:
        return None
    return int((snapshot - buyer.date.max()).days)


def days_since_any_activity(activities: pd.DataFrame, snapshot: pd.Timestamp = SNAPSHOT) -> int | None:
    return None if activities.empty else int((snapshot - activities.date.max()).days)

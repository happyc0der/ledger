import pandas as pd

from conftest import AS_OF, make_company
from ledger.tools import days_since_buyer_touch, deal_amount, list_price, normalize_product, pipeline_total


def test_product_normalisation_and_price():
    products = pd.DataFrame([{"product": "GTX Pro", "series": "GTX", "sales_price": 4821}])
    assert normalize_product("GTXPro") == normalize_product("GTX Pro")
    assert list_price(products, "GTXPro") == 4821 and list_price(products, "Nope") is None


def test_amount_falls_back_to_catalogue_then_zero(one_deal):
    products = pd.DataFrame([{"product": "GTX Basic", "series": "GTX", "sales_price": 550}])
    assert deal_amount(products, pd.Series({**one_deal, "amount": None})) == 550
    assert deal_amount(pd.DataFrame(columns=["product", "sales_price"]), pd.Series({**one_deal, "amount": None})) == 0.0


def test_buyer_touch_ignores_rep_and_system(one_deal):
    co = make_company([one_deal], [("a", "D1", "2026-10-01", "email", "Priya Okafor", "hi"),
                                   ("b", "D1", "2026-10-15", "call", "Rep One", "Left VM"),
                                   ("c", "D1", "2026-10-16", "email", "system", "Auto-reply: out of office")],
                      contacts=[{"opportunity_id": "D1", "name": "Priya Okafor", "title": "IT", "role": "champion"}])
    assert days_since_buyer_touch(co.activities_for("D1"), "Rep One", AS_OF) == 18
    assert pipeline_total(co.products, co.deals) == 550

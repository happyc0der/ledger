import json
from pathlib import Path

import pandas as pd
import pytest

from ledger.ingest import _stage, ingest

FX = Path(__file__).parent / "fixtures" / "hubspot"


def test_stage_mapping():
    assert _stage("contractsent", {"contractsent": "Negotiation"}) == "Negotiation"
    assert _stage("Proposal/Price Quote", {}) == "Proposal"
    assert _stage("Technical Validation", {}) is None  # custom stage: kept, not dropped


def test_hubspot_roundtrip_keeps_custom_stage_and_attributes_by_direction(tmp_path):
    rep = ingest("hubspot", tmp_path, deals=FX / "deals.csv", activities=FX / "engagements.csv")
    d = pd.read_csv(tmp_path / "deals.csv")
    assert set(d.opportunity_id.astype(str)) == {"101", "102"}          # closedwon dropped
    assert d.set_index("opportunity_id").loc[102, "stage_raw"] == "Technical Validation"
    assert rep["deals"]["kept_unmapped_stage"] == {"Technical Validation": 1}
    assert rep["attribution"]["buyer"] == 2 and rep["attribution"]["rep"] == 1  # owner-credited rows resolved by direction
    assert json.loads((tmp_path / "profile.json").read_text())["source"] == "default"
    assert (tmp_path / "history.csv").exists()


def test_ingest_refuses_when_nothing_is_attributable(tmp_path):
    eng = pd.read_csv(FX / "engagements.csv").drop(columns=["Email direction", "From address"])
    eng.to_csv(tmp_path / "eng.csv", index=False)
    with pytest.raises(SystemExit):
        ingest("hubspot", tmp_path / "out", deals=FX / "deals.csv", activities=tmp_path / "eng.csv")
    ingest("hubspot", tmp_path / "out2", deals=FX / "deals.csv", activities=tmp_path / "eng.csv", allow_no_buyer=True)

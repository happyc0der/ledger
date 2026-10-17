"""The decision layer: typed questions → calibrated probabilities.

Primary backend is Jev (TypeSafe System One): it returns a probability for a yes/no
question and a distribution over options for a choice, and it is trained to be
calibrated. Fallback backend asks the local language model for the same numbers via a
JSON schema — which is *not* calibrated, and that is part of the v1-vs-v2 story.
Both return the same Decision so the agent doesn't care which is behind it.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass

from . import llm
from .config import ACTIONS, BASE_WIN_RATE, CACHE_DIR, OBJECTIONS

OBJECTION_DESC = {
    "none": "no blocking objection; buyer is moving toward purchase",
    "budget": "price or budget is the blocker (too expensive, capex frozen, no budget line)",
    "competitor": "buyer is comparing with or leaning toward a competing vendor",
    "timing": "buyer has gone silent or pushed the decision out with no date",
    "authority": "the contact cannot buy: champion left, or does not own the budget/decision",
    "need": "product does not meet a stated requirement (feature gap)",
}
ACTION_DESC = {
    "confirm_procurement_timeline": "buyer is committed; lock down PO/legal/signature dates",
    "send_roi_business_case": "quantify value to unlock a stuck budget conversation",
    "offer_phased_pricing": "restructure payment/units to fit budget",
    "run_competitive_bakeoff": "prove superiority head-to-head against the named competitor",
    "multithread_to_economic_buyer": "get to the person who owns the budget/decision",
    "re_engage_dormant": "one structured attempt to revive a silent buyer",
    "disqualify": "stop working this deal for now (no budget, no fit, no path)",
}


@dataclass
class Decision:
    win_probability: float
    objection: str
    objection_probs: dict
    next_action: str
    action_probs: dict
    backend: str
    latency_ms: int


def backend_name() -> str:
    forced = os.getenv("DECIDE_BACKEND")
    if forced:
        return forced
    return "jev" if os.getenv("TYPESAFE_API_KEY") else "llm"


def _model_tag(backend: str) -> str:
    """The decision depends on who decided: Jev, or a specific provider/model behind the LLM fallback."""
    if backend != "llm":
        return backend
    from .config import provider
    p = provider()
    return f"{p.name}/{p.model}"


def _cache_path(state: dict, backend: str):
    h = hashlib.sha256(json.dumps([backend, _model_tag(backend), state], sort_keys=True).encode()).hexdigest()[:24]
    d = CACHE_DIR.parent / "decide"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def _jev(state: dict) -> Decision:
    from typesafe_sdk import Choice, Noul, TypeSafeClient
    client = TypeSafeClient()
    t0 = time.time()
    r = client.system_one(state, {
        "win": Noul(instructions="Will this opportunity close as Won (the buyer purchases) within the "
                                 "next 90 days, given the CRM record and what the buyer said? Historically "
                                 f"{int(BASE_WIN_RATE * 100)}% of this company's deals are won."),
        "objection": Choice(instructions="What is the main objection the buyer raised at any point in this "
                                         "record, even if it was later resolved? Judge by the buyer's own "
                                         "words, not the rep's optimism. 'none' only if the buyer never raised one.",
                            criteria=OBJECTION_DESC),
        "action": Choice(instructions="What is the single best next action for the rep this week?",
                         criteria=ACTION_DESC),
    })
    ms = int((time.time() - t0) * 1000)
    a = r.answers

    def probs(ans):
        p = getattr(ans, "probabilities", None) or {}
        return {k: float(v) for k, v in dict(p).items()}
    return Decision(float(a["win"].noul), a["objection"].choice, probs(a["objection"]),
                    a["action"].choice, probs(a["action"]), "jev", ms)


_LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "buyer_evidence": {"type": "string"},
        "objection": {"type": "string", "enum": OBJECTIONS},
        "objection_confidence": {"type": "number"},
        "next_action": {"type": "string", "enum": ACTIONS},
        "action_confidence": {"type": "number"},
        "win_probability": {"type": "number"},
    },
    "required": ["buyer_evidence", "objection", "objection_confidence", "next_action",
                 "action_confidence", "win_probability"],
}


def _spread(choice: str, conf: float, keys: list[str]) -> dict:
    """Turn (choice, confidence) into a distribution: confidence on the choice, rest spread evenly."""
    conf = min(max(float(conf), 1 / len(keys)), 1.0)
    rest = (1 - conf) / (len(keys) - 1)
    return {k: (conf if k == choice else rest) for k in keys}


def _llm(state: dict, *, version: str, session_id: str) -> Decision:
    system = ("You are the decision model for a B2B pipeline review. Judge ONLY by what the buyer "
              "said or did (activities authored by the buyer, or buyer quotes inside rep notes), never "
              "by the rep's stage or optimism. First write buyer_evidence: the single most decision-"
              "relevant thing the buyer said, in a few words. Then choose objection: the main objection the "
              "buyer raised at ANY point in the record, even if later resolved ('none' only if the buyer "
              "never raised one), from "
              f"{json.dumps(OBJECTION_DESC)} and next_action from {json.dumps(ACTION_DESC)}, each with a "
              "confidence 0-1. Finally win_probability: chance this closes Won within 90 days; the "
              f"company base rate is {BASE_WIN_RATE}, so go well below it when the buyer has frozen "
              "budget, left, chosen a competitor, gone silent for weeks, or named a missing feature, "
              "and well above it when the buyer is routing paperwork, approved budget, or asked for a quote.")
    t0 = time.time()
    _, parsed = llm.chat([{"role": "system", "content": system},
                          {"role": "user", "content": json.dumps(state, indent=1, default=str)}],
                         schema=_LLM_SCHEMA, version=version, session_id=session_id,
                         metadata={"role": "decide-fallback"})
    ms = int((time.time() - t0) * 1000)
    parsed = parsed or {}
    obj = parsed.get("objection") if parsed.get("objection") in OBJECTIONS else "none"
    act = parsed.get("next_action") if parsed.get("next_action") in ACTIONS else "re_engage_dormant"
    p_win = float(parsed.get("win_probability", BASE_WIN_RATE))
    return Decision(min(max(p_win, 0), 1), obj,
                    _spread(obj, parsed.get("objection_confidence", 0.6), OBJECTIONS),
                    act, _spread(act, parsed.get("action_confidence", 0.6), ACTIONS), "llm", ms)


def decide(state: dict, *, version: str, session_id: str) -> Decision:
    state = {k: v for k, v in state.items() if not k.startswith("_")}
    b = backend_name()
    cp = _cache_path(state, b)
    if cp.exists():
        return Decision(**json.loads(cp.read_text()))
    d = _jev(state) if b == "jev" else _llm(state, version=version, session_id=session_id)
    if b == "llm" and getattr(llm.LAST_USED, "value", None) not in (None, _model_tag(b)):
        return d  # answered by the fallback provider: usable now, never remembered as this model's decision
    cp.write_text(json.dumps(asdict(d)))
    return d

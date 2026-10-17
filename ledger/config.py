"""Environment, provider selection and constants. Everything free/cheap by design."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

COMPANY_DIR = Path(os.getenv("LEDGER_DATA", ROOT / "data" / "company"))  # any ingested dataset
DATASET = COMPANY_DIR.name
RUNS_DIR = ROOT / "runs" / DATASET   # runs/<dataset>/<version>.jsonl = latest; runs/<dataset>/<as_of>/<version>/ = history
DB_PATH = RUNS_DIR / "ledger.db"


def run_dir(as_of, version: str) -> Path:
    return RUNS_DIR / str(pd.Timestamp(as_of).date()) / version
CACHE_DIR = ROOT / ".cache" / "llm"
SNAPSHOT = pd.Timestamp(os.getenv("LEDGER_AS_OF", "2026-10-19"))  # "today" for the review

OBJECTIONS = ["none", "budget", "competitor", "timing", "authority", "need"]


@dataclass
class Settings:
    """Per-company knobs. Defaults are the demo company's; a real dataset overrides them with
    data/<name>/ledger.json (RevOps-owned) and, for the historical ones, data/<name>/profile.json
    (learned by ingest from closed deals)."""
    promise_days: int = 14          # buyer promise older than this with no reply = expired
    dormant_days: int = 30          # no activity at all
    frozen_window_days: int = 75    # close date inside this window contradicts "budget frozen / paused"
    median_cycle_days: int = 57     # stalled = 2x this in an early stage
    stalled_multiplier: float = 2.0
    base_win_rate: float = 0.63
    late_stages: tuple = ("Proposal", "Negotiation")
    commit_p: float = 0.7           # forecast bands
    best_case_p: float = 0.4
    disabled_checks: tuple = ()
    source: dict | None = None      # where each learned value came from

    @classmethod
    def load(cls, data_dir: Path) -> "Settings":
        import json
        vals, src = {}, {}
        prof = data_dir / "profile.json"
        if prof.exists():
            pj = json.loads(prof.read_text())
            for k in ("base_win_rate", "median_cycle_days", "dormant_days"):
                if k in pj:
                    vals[k] = pj[k]; src[k] = f"learned from {pj.get('n_closed', '?')} closed deals"
        cfg = data_dir / "ledger.json"
        if cfg.exists():
            for k, v in json.loads(cfg.read_text()).items():
                if k in cls.__dataclass_fields__:
                    vals[k] = tuple(v) if isinstance(v, list) else v; src[k] = "ledger.json"
        return cls(**vals, source=src)


SETTINGS = Settings.load(COMPANY_DIR)
BASE_WIN_RATE = SETTINGS.base_win_rate
ACTIONS = [
    "confirm_procurement_timeline",
    "send_roi_business_case",
    "offer_phased_pricing",
    "run_competitive_bakeoff",
    "multithread_to_economic_buyer",
    "re_engage_dormant",
    "disqualify",
]


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str


PROVIDERS = {
    # Local, unlimited, offline. Ollama speaks the OpenAI protocol at /v1 and its own at /api.
    "ollama": lambda: Provider("ollama", os.getenv("OLLAMA_URL", "http://localhost:11434"),
                               "ollama", os.getenv("OLLAMA_MODEL", "qwen3:14b")),
    # Free tier: ~1k requests/day. Model id configurable because Groq rotates its free list.
    "groq": lambda: Provider("groq", "https://api.groq.com/openai/v1",
                             os.environ["GROQ_API_KEY"], os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")),
    # Free tier via Google AI Studio; OpenAI-compatible endpoint, key as bearer token.
    "gemini": lambda: Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
                               os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")),
    # $25 sign-up credit. Only if we want a bigger model on demo day.
    "xai": lambda: Provider("xai", "https://api.x.ai/v1",
                            os.environ["XAI_API_KEY"], os.getenv("XAI_MODEL", "grok-4-fast")),
    # Money Talks 2 technology sponsor: one OpenAI-compatible key for 80+ models ("provider/model").
    # Event credits ($260/participant) expire 2026-10-18 18:00 ET. Model ids: nicrron.ai/docs/models.
    "nicrron": lambda: Provider("nicrron", os.getenv("NICRRON_URL", "https://api.nicrron.ai/v1"),
                                os.environ["NICRRON_API_KEY"], os.getenv("NICRRON_MODEL", "anthropic/claude-sonnet-5-5")),
}


def provider(name: str | None = None) -> Provider:
    return PROVIDERS[name or os.getenv("LLM_PROVIDER", "ollama")]()

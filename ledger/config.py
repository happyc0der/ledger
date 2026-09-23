"""Environment, provider selection and constants. Everything free/cheap by design."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

COMPANY_DIR = ROOT / "data" / "company"
RUNS_DIR = ROOT / "runs"
CACHE_DIR = ROOT / ".cache" / "llm"
SNAPSHOT = pd.Timestamp("2026-10-19")
BASE_WIN_RATE = 0.63

OBJECTIONS = ["none", "budget", "competitor", "timing", "authority", "need"]
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
}


def provider(name: str | None = None) -> Provider:
    return PROVIDERS[name or os.getenv("LLM_PROVIDER", "ollama")]()

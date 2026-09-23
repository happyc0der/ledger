"""Rewrite every templated activity so 228 deals read like 228 different people wrote them.

Uses the local model. Facts are preserved and checked: every person, product, competitor
name and every number in the original must survive, or the original is kept. Originals
are saved to activities_original.csv. Idempotent via a per-row cache.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ledger import llm  # noqa: E402
from ledger.config import COMPANY_DIR  # noqa: E402

VOICES = ["terse, lowercase, no punctuation fuss", "formal and complete sentences", "friendly and chatty",
          "bullet-like fragments", "hurried, typed on a phone", "precise and technical"]
SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
TOKEN = re.compile(r"[A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)?|\$?\d[\d,]*%?")


def must_keep(text: str) -> set[str]:
    skip = {"Buyer", "Left", "VM", "Sent", "Thanks", "Update", "Heads", "Sorry", "Yes", "Legal", "PO", "MSA",
            "Engineering", "Procurement", "January", "Q4", "Being", "After", "Order", "One", "Appreciate",
            "Nothing", "Checked", "Side", "Great", "Good", "Demo", "Intro", "Pricing", "Spoke", "Discovery",
            "Technical", "Proposal", "Requirements", "Solid", "Auto", "For", "We", "The", "Their", "Main",
            "Same", "Expect", "Going", "Not", "Can", "Still", "Going", "Honestly", "Fit", "Replacing", "Forwarded"}
    return {t for t in TOKEN.findall(text) if t not in skip and not t.endswith("day")}


def main():
    rng = random.Random(7)
    src = COMPANY_DIR / "activities.csv"
    orig = COMPANY_DIR / "activities_original.csv"
    if not orig.exists():
        orig.write_bytes(src.read_bytes())  # copy, never move: a crash must not lose the file
    df = pd.read_csv(orig)
    out, kept = [], 0
    for i, r in enumerate(df.itertuples()):
        voice = VOICES[hash(r.author) % len(VOICES)]
        system = (f"Rewrite this CRM {r.type} note in the voice of its author ({r.author}), style: {voice}. "
                  "Keep every fact, name, number, product, competitor and the meaning exactly; keep any "
                  "quoted buyer sentence as a quote (you may reword it slightly). Change sentence structure "
                  "and wording; vary length. Return JSON {\"text\": ...} only.")
        _, parsed = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": r.text}],
                             schema=SCHEMA, version="paraphrase", session_id="paraphrase",
                             metadata={"activity_id": r.activity_id}, num_ctx=4096)
        new = (parsed or {}).get("text", "").strip()
        missing = {t for t in must_keep(r.text) if t.lower() not in new.lower()}
        if not new or missing or len(new) < 0.5 * len(r.text):
            new, kept = r.text, kept + 1
        out.append(new)
        if i % 50 == 0:
            print(f"{i}/{len(df)} kept-original so far: {kept}", flush=True)
    df["text"] = out
    df.to_csv(src, index=False)
    print(f"done: {len(df)} activities, {kept} kept original")


if __name__ == "__main__":
    main()

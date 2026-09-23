"""Rewrite every templated activity so 228 deals read like 228 different people wrote them.

Facts are checked both ways: every name and number in the original must survive, and the
rewrite may not ADD anything — no new names, numbers, times, emails, phones, companies or
relatives. (The first version only checked the first direction; the local model invented
phone numbers and "my sister" and PRISM's PII guardrail caught it.) Two attempts, then the
original is kept. Originals live in activities_original.csv.
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
ADDED = [re.compile(x, re.I) for x in (r"[\w.+-]+@[\w-]+\.\w+", r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
                                         r"\b\d{1,2}:\d{2}\b", r"\b(sister|brother|wife|husband|mother|father|cousin)\b",
                                         r"\b(salesforce|hubspot|crm|linkedin|zoom|slack)\b")]
NUM = re.compile(r"\d[\d,.]*")
CAP = re.compile(r"(?<![.!?\n]\s)(?<!^)(?<![.!?])\b[A-Z][a-z]+\b")  # capitalised, not at a sentence start
COMMON = {"Buyer", "Left", "VM", "Sent", "Thanks", "Update", "Heads", "Sorry", "Yes", "Legal", "PO", "MSA", "Hi", "Hey",
          "Engineering", "Procurement", "January", "Q4", "Being", "After", "Order", "One", "Appreciate", "Quick", "Call",
          "Nothing", "Checked", "Side", "Great", "Good", "Demo", "Intro", "Pricing", "Spoke", "Discovery", "Team", "The",
          "Technical", "Proposal", "Requirements", "Solid", "Auto", "For", "We", "Their", "Main", "Same", "Expect", "Going",
          "Not", "Can", "Still", "Honestly", "Fit", "Replacing", "Forwarded", "Just", "Also", "Will", "Our", "They", "He",
          "She", "It", "This", "That", "No", "So", "And", "But", "Had", "Has", "Have", "Met", "Talked", "Followed", "Emailed",
          "Note", "Notes", "Meeting", "Email", "Reached", "Confirmed", "Discussed", "Reviewed", "Pending", "Next", "Then",
          "Today", "Tomorrow", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Week", "Budget", "Finance", "Security",
          "Firmware", "Loaner", "Lab", "Site", "Sites", "Roadmap", "Spec", "Quote", "Ok", "Okay", "Got", "Sounds", "Looks",
          "Need", "Needs", "Waiting", "Trying", "Left", "Voicemail", "Approved", "Signed", "Moving", "Decision", "Decided",
          "Update", "Re", "Fyi", "Per", "Since", "Once", "If", "When", "What", "Where", "Who", "Why", "How", "Which", "There",
          "Here", "Now", "Later", "Soon", "Very", "Really", "Definitely", "Probably", "Maybe", "Unfortunately", "Hopefully"}


def added_facts(orig: str, new: str) -> list[str]:
    bad = [p.pattern[:20] for p in ADDED if p.search(new) and not p.search(orig)]
    onums = set(NUM.findall(orig))
    bad += [n for n in NUM.findall(new) if n not in onums and n.strip(",.") not in {x.strip(",.") for x in onums}]
    olower = orig.lower()
    mid = [m.group(0) for m in re.finditer(r"\b[A-Z][a-z]+\b", new)
           if m.start() > 0 and not re.search(r"[.!?:\-\n]\s*$|^\s*$", new[max(0, m.start() - 3):m.start()])]
    bad += [c for c in mid if c.lower() not in olower and c not in COMMON]
    if len(new) > 1.5 * len(orig) + 40:
        bad.append("too long")
    return bad


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
        system += (" Do NOT add anything that is not in the original: no new names, companies, tools, numbers, "
                   "times, contact details, relatives or events. Rewording only.")
        new = ""
        for attempt in range(2):
            msgs = [{"role": "system", "content": system + (" (Attempt 2: keep it shorter and closer to the original.)" if attempt else "")},
                    {"role": "user", "content": r.text}]
            try:
                _, parsed = llm.chat(msgs, schema=SCHEMA, version="paraphrase", session_id="paraphrase",
                                     metadata={"activity_id": r.activity_id, "attempt": attempt}, num_ctx=4096)
            except Exception as e:  # one bad row must not kill the pass
                print(f"row {r.activity_id} attempt {attempt}: {type(e).__name__}: {str(e)[:80]}", flush=True)
                parsed = None
            cand = (parsed or {}).get("text", "").strip()
            missing = {t for t in must_keep(r.text) if t.lower() not in cand.lower()}
            if cand and not missing and len(cand) >= 0.5 * len(r.text) and not added_facts(r.text, cand):
                new = cand
                break
        if not new:
            new, kept = r.text, kept + 1
        out.append(new)
        if i % 50 == 0:
            print(f"{i}/{len(df)} kept-original so far: {kept}", flush=True)
    df["text"] = out
    df.to_csv(src, index=False)
    print(f"done: {len(df)} activities, {kept} kept original")


if __name__ == "__main__":
    main()

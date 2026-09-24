"""Who said it? Real CRM exports credit every logged email and call to the deal owner, so
"buyer said" cannot be read off the author column. This resolves a speaker for every activity
from the strongest evidence available, and never promotes "unknown" to "buyer":

  1. direction          (HubSpot hs_email_direction / hs_call_direction, Salesforce Incoming)
  2. from-address domain (the team's own domains → rep; any other → buyer)
  3. auto-reply patterns → system
  4. author name        (a contact on the deal/account → buyer; a rep/manager → rep)
  5. unknown

Rep-authored notes can still contain buyer words: `Buyer: "..."`, quoted lines (`> `), and
forwarded/replied mail under `From:` / `On ... wrote:` headers. segments() marks those spans
so the verifier can accept a quote from inside a rep note when it is clearly the buyer's.
"""
from __future__ import annotations

import re

AUTO_REPLY = re.compile(r"auto-?matic reply|auto-?reply|out of (the )?office|no longer with|is no longer (at|with|employed)"
                        r"|undeliverable|delivery (has )?failed|mailer-daemon", re.I)
INBOUND = {"inbound", "incoming", "incoming_email", "received", "in"}
OUTBOUND = {"outbound", "outgoing", "outgoing_email", "sent", "out", "email", "forwarded_email"}
HEADER = re.compile(r"(^|\n)\s*(from:\s*(?P<from>[^\n]+)|on .{6,80}? wrote:)", re.I)
BUYER_TAG = re.compile(r"(?:buyer|customer|client|prospect|\bthey\b)\s*(?:said|says|wrote|:)\s*[\"“]?(?P<q>[^\"”\n]{8,})[\"”]?", re.I)
QUOTED_LINE = re.compile(r"^\s*>\s?(.+)$", re.M)


def domain(addr: str | None) -> str:
    if not addr or "@" not in str(addr):
        return ""
    return str(addr).rsplit("@", 1)[1].strip().lower().strip(">")


def _tokens(name: str | None) -> set[str]:
    return {t.lower() for t in re.split(r"[\s,]+", str(name or "")) if len(t) > 1}


def speaker(row: dict, *, rep: str, contact_names: set[str], team_names: set[str], own_domains: set[str],
            contact_domains: set[str] = frozenset()) -> tuple[str, str]:
    """Returns (speaker, basis) with speaker ∈ buyer | rep | system | unknown."""
    text = str(row.get("text") or "")
    direction = str(row.get("direction") or "").strip().lower()
    if direction in INBOUND:
        return "buyer", "direction"
    if direction in OUTBOUND:
        return "rep", "direction"
    fd = domain(row.get("from_addr"))
    if fd:
        if fd in own_domains:
            return "rep", "from-domain"
        if not contact_domains or fd in contact_domains:
            return "buyer", "from-domain"
    if AUTO_REPLY.search(text[:300]) or str(row.get("author") or "").lower() == "system":
        return "system", "auto-reply"
    author = str(row.get("author") or "")
    at = _tokens(author)
    if at and any(at & _tokens(c) and len(at & _tokens(c)) >= 1 and (at <= _tokens(c) or _tokens(c) <= at) for c in contact_names):
        return "buyer", "author-contact"
    if author and (author == rep or any(at <= _tokens(t) or _tokens(t) <= at for t in team_names if _tokens(t))):
        return "rep", "author-rep"
    return "unknown", "no-signal"


def segments(text: str) -> list[tuple[str, str]]:
    """Spans inside a note attributed to someone other than its author.
    Returns [(kind, span)] with kind ∈ quoted_buyer | forwarded."""
    out = []
    for m in BUYER_TAG.finditer(text):
        out.append(("quoted_buyer", m.group("q").strip()))
    for m in re.finditer(r"[\"“]([^\"”]{8,})[\"”]", text):  # any quoted sentence in a rep note
        out.append(("quoted_buyer", m.group(1).strip()))
    quoted = QUOTED_LINE.findall(text)
    if quoted:
        out.append(("quoted_buyer", " ".join(q.strip() for q in quoted)))
    h = HEADER.search(text)
    if h:
        out.append(("forwarded", text[h.end():].strip()))
    return out


def annotate(activities, deals, contacts, team):
    """Add speaker / speaker_basis columns to an activities frame (used once at load)."""
    import pandas as pd
    a = activities.copy()
    if a.empty:
        a["speaker"] = pd.Series(dtype=str); a["speaker_basis"] = pd.Series(dtype=str)
        return a
    rep_of = dict(zip(deals.opportunity_id, deals.sales_agent))
    team_names = set(deals.sales_agent.dropna()) | set(team.get("manager", pd.Series(dtype=str)).dropna())
    own = set()
    for col in ("email", "from_addr"):
        if col in team.columns:
            own |= {domain(x) for x in team[col].dropna()}
    if "from_addr" in a.columns and "to_addr" in a.columns:  # the team's domain is whoever sends outbound mail most
        pass
    contacts_by_deal = contacts.groupby("opportunity_id").name.apply(set).to_dict() if len(contacts) else {}
    cdom = {domain(x) for x in contacts["email"].dropna()} if "email" in contacts.columns else set()
    sp, basis = [], []
    for r in a.to_dict("records"):
        s, b = speaker(r, rep=rep_of.get(r["opportunity_id"], ""), contact_names=contacts_by_deal.get(r["opportunity_id"], set()),
                       team_names=team_names, own_domains=own, contact_domains=cdom)
        sp.append(s); basis.append(b)
    a["speaker"], a["speaker_basis"] = sp, basis
    return a

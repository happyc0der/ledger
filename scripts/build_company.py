"""Build the demo company ("Vireo Systems") from the Maven CRM dataset.

Takes the real deals that were open on the snapshot date, shifts every date so the
snapshot lands on the Monday after the hackathon, and layers on synthetic CRM
activity (calls, emails, meetings) whose content is conditioned on the deal's
real, later outcome. The outcome itself is hidden from the agent.

Outputs (data/company/):
  company.md          one-page brief of the fictional company (agent-readable)
  products.csv        catalogue with list prices (note: pipeline spells "GTX Pro" as "GTXPro")
  team.csv            reps, manager, office
  accounts.csv        account firmographics
  deals.csv           AGENT-VISIBLE snapshot of the open pipeline (no outcomes)
  contacts.csv        buyer contacts per deal
  activities.csv      AGENT-VISIBLE call notes / emails / meetings
  ground_truth.csv    HIDDEN: real outcome, planted objection, correct next action
"""
from __future__ import annotations

import random
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data"
OUT = ROOT / "data" / "company"

SEED = 26
COMPANY = "Vireo Systems"
MANAGER = "Melvin Marxen"
SOURCE_SNAPSHOT = pd.Timestamp("2017-07-01")
DEMO_SNAPSHOT = pd.Timestamp("2026-10-19")  # Monday pipeline review after the (postponed) hackathon
SHIFT = DEMO_SNAPSHOT - SOURCE_SNAPSHOT

rng = random.Random(SEED)

FIRST = ["Priya", "Marcus", "Elena", "Tom", "Aisha", "Daniel", "Grace", "Omar", "Hannah", "Victor",
         "Leah", "Samuel", "Nadia", "Ethan", "Ruth", "Jorge", "Mei", "Patrick", "Sofia", "Kwame",
         "Ingrid", "Raj", "Clara", "Ben", "Yuki", "Andre", "Fatima", "Luke", "Ines", "Noah"]
LAST = ["Okafor", "Lindqvist", "Marchetti", "Reyes", "Whitfield", "Nakamura", "Adeyemi", "Kowalski",
        "Fischer", "Delgado", "Brennan", "Haddad", "Osei", "Petrov", "Sandoval", "Mensah", "Thornton",
        "Ivanova", "Castellano", "Bergström", "Quinn", "Abara", "Moreau", "Sato", "Hughes", "Farouk"]

ECON_TITLES = ["VP Infrastructure", "CIO", "Head of IT Operations", "VP Engineering", "CTO"]
CHAMP_TITLES = ["IT Manager", "Infrastructure Lead", "Systems Engineer", "Platform Engineering Manager",
                "Procurement Analyst"]
COMPETITORS = ["Kestrel Compute", "Bluewater Systems", "Orion Hardware"]

OBJECTIONS = ["none", "budget", "competitor", "timing", "authority", "need"]
ACTIONS = [
    "confirm_procurement_timeline",   # deal is real, drive it to signature
    "send_roi_business_case",         # budget objection, quantify value
    "offer_phased_pricing",           # budget objection, restructure
    "run_competitive_bakeoff",        # competitor in play, prove it
    "multithread_to_economic_buyer",  # champion weak/gone, go up
    "re_engage_dormant",              # buyer silent, one structured re-engage
    "disqualify",                     # stop working it
]


def person():
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


# ---------------------------------------------------------------------------
# Archetypes. Each is keyed on the REAL outcome and produces a believable story.
# `stage` is the rep-set CRM stage (may be optimistic); `gap` is days since the
# buyer last responded; `steps` are activity templates in chronological order.
# {champ}, {econ}, {comp}, {product}, {price}, {rep}, {account} are filled in.
# ---------------------------------------------------------------------------
WON = [
    dict(name="clean_run", objection="none", action="confirm_procurement_timeline",
         stage="Negotiation", gap=(2, 9), inflated=False, steps=[
             ("call", "rep", "Discovery with {champ}. Replacing end-of-life units across two sites. "
                             "Buyer: \"We need this racked before the Q4 freeze.\""),
             ("email", "buyer", "Thanks {rep}. Forwarded the {product} spec to {econ} — she wants a "
                                "single-quote for both sites. Can you send a formal proposal?"),
             ("meeting", "rep", "Proposal review with {champ} and {econ}. {econ} approved budget at "
                                "list ({price}). Procurement is drafting the PO; legal has our MSA."),
             ("email", "buyer", "PO is with procurement. Expect signature in the next two weeks."),
         ]),
    dict(name="price_resolved", objection="budget", action="confirm_procurement_timeline",
         stage="Proposal", gap=(3, 12), inflated=False, steps=[
             ("call", "rep", "Demo of {product} with {champ}. Fit is good. Buyer: \"Honestly the "
                             "number is higher than what we budgeted.\""),
             ("email", "rep", "Sent {champ} a phased option: 60% of units this quarter, remainder in "
                              "January. Same unit price."),
             ("call", "rep", "{champ} took the phased structure to {econ}. Buyer: \"The split works "
                             "for us — finance is fine with two POs.\" Sending order form."),
             ("email", "buyer", "Order form received, routing for signature."),
         ]),
    dict(name="bakeoff_won", objection="competitor", action="confirm_procurement_timeline",
         stage="Negotiation", gap=(1, 8), inflated=False, steps=[
             ("call", "rep", "{champ} confirmed they are also evaluating {comp}. Main criterion is "
                             "failover performance."),
             ("meeting", "rep", "Side-by-side test at customer lab. {product} beat {comp} on failover "
                                "recovery. Buyer: \"That settles it for the engineering team.\""),
             ("email", "buyer", "Engineering recommendation went to {econ} in favour of {product}. "
                                "Please send the final quote."),
         ]),
    dict(name="quiet_late_stage", objection="none", action="confirm_procurement_timeline",
         stage="Proposal", gap=(14, 24), inflated=False, steps=[
             ("meeting", "rep", "Technical review with {champ}'s team. All requirements met. "
                                "Buyer: \"We're going to move on this; it just has to clear legal.\""),
             ("email", "buyer", "Legal is reviewing the MSA. Nothing needed from you for now — I'll "
                                "come back once redlines are in."),
         ]),
    dict(name="reopened_then_closed", objection="competitor", action="confirm_procurement_timeline",
         stage="Negotiation", gap=(3, 10), inflated=False, steps=[
             ("call", "rep", "{champ} mentioned {comp} came in with a lower number."),
             ("email", "buyer", "We compared both. Going with {product} — the support model won it. Legal has the MSA."),
             ("email", "buyer", "One more thing before signature: our security team wants the firmware-signing "
                                "doc for {product}. Can you send it this week? Not a blocker, just a checkbox."),
         ]),
    dict(name="noisy_rep", objection="none", action="confirm_procurement_timeline",
         stage="Proposal", gap=(5, 12), inflated=False, steps=[
             ("call", "rep", "Left VM for {champ} re: {product} proposal."),
             ("call", "rep", "Left VM."),
             ("email", "buyer", "Sorry {rep}, been travelling. Yes, we're moving ahead — {econ} approved it. "
                                "PO should go out next week."),
             ("call", "rep", "Left VM to confirm PO timing."),
         ]),
    dict(name="silent_then_signed", objection="timing", action="re_engage_dormant",
         stage="Proposal", gap=(25, 40), inflated=False, steps=[
             ("call", "rep", "Discovery with {champ}; needs {product} for a site refresh."),
             ("email", "rep", "Sent proposal and pricing."),
             ("email", "buyer", "Things are hectic here — haven't forgotten about this. Let me get back to you."),
             ("call", "rep", "Left VM."),
         ]),
    dict(name="budget_unresolved_won", objection="budget", action="offer_phased_pricing",
         stage="Proposal", gap=(5, 14), inflated=False, steps=[
             ("call", "rep", "Demo of {product} for {champ}'s team."),
             ("email", "buyer", "Team liked it. The number is a stretch for this quarter's budget though — is "
                                "there any flexibility on structure?"),
             ("call", "rep", "Discussed options with {champ}. No answer yet; she will talk to {econ}."),
         ]),
    dict(name="stage_lagging", objection="none", action="confirm_procurement_timeline",
         stage="Qualification", gap=(2, 7), inflated=False, steps=[
             ("call", "rep", "Intro with {champ}. Existing customer expanding to a new site."),
             ("email", "buyer", "We've decided to standardise on {product} for the new site. "
                                "{econ} signed off; can you send the paperwork this week?"),
         ]),
]

LOST = [
    dict(name="budget_frozen", objection="budget", action="disqualify",
         stage="Proposal", gap=(20, 45), inflated=True, steps=[
             ("call", "rep", "Good discovery with {champ}. Clear need for {product}."),
             ("email", "buyer", "Update from our side: {econ} froze all new capex until the next fiscal "
                                "year. I still want to do this, but there is no budget line right now."),
             ("call", "rep", "Left voicemail for {champ}. Still think we can pull this into this quarter."),
         ]),
    dict(name="competitor_leaning", objection="competitor", action="run_competitive_bakeoff",
         stage="Negotiation", gap=(10, 25), inflated=True, steps=[
             ("call", "rep", "Pricing call with {champ}. They have a quote from {comp} as well."),
             ("email", "buyer", "Being transparent: the team is leaning toward {comp}. Their price is "
                                "lower and the integration with our monitoring stack is already done."),
             ("call", "rep", "Spoke with {champ}. Reiterated our roadmap. Feel we are still in it."),
         ]),
    dict(name="champion_left", objection="authority", action="multithread_to_economic_buyer",
         stage="Proposal", gap=(25, 50), inflated=True, steps=[
             ("meeting", "rep", "Great session with {champ}; he will push {product} internally."),
             ("email", "rep", "Sent proposal to {champ}."),
             ("email", "auto", "Auto-reply: {champ} is no longer with {account}. For infrastructure "
                               "enquiries please contact {econ}."),
         ]),
    dict(name="ghosted", objection="timing", action="re_engage_dormant",
         stage="Proposal", gap=(40, 70), inflated=True, steps=[
             ("call", "rep", "Solid first call with {champ}. Interested in {product} for a refresh."),
             ("email", "rep", "Sent pricing and datasheet."),
             ("call", "rep", "Left VM."),
             ("call", "rep", "Left VM again. Will keep trying."),
         ]),
    dict(name="feature_gap", objection="need", action="disqualify",
         stage="Discovery", gap=(8, 20), inflated=False, steps=[
             ("call", "rep", "Requirements call with {champ}."),
             ("email", "buyer", "After the technical review: we need native support for our SAN fabric, "
                                "which {product} doesn't have. Unless that's on your roadmap this year we "
                                "can't proceed."),
         ]),
    dict(name="looked_healthy", objection="timing", action="re_engage_dormant",
         stage="Negotiation", gap=(15, 35), inflated=True, steps=[
             ("meeting", "rep", "Great demo with {champ}'s team. Buyer: \"This is exactly what we need, let's do it.\""),
             ("email", "rep", "Sent proposal for {product}."),
             ("email", "buyer", "Heads-up: we've been asked to pause all new vendor onboarding until the reorg "
                                "settles. Nothing to do with you — I'll reach out when I can."),
             ("call", "rep", "Checked in with {champ}. Still very warm, expect this to close this quarter."),
         ]),
    dict(name="competitor_decided", objection="competitor", action="disqualify",
         stage="Proposal", gap=(6, 18), inflated=True, steps=[
             ("call", "rep", "Pricing discussion with {champ}. {comp} is also bidding."),
             ("email", "rep", "Sent revised quote for {product}."),
             ("email", "buyer", "Appreciate the quick turnaround. We've decided to go with {comp} for this "
                                "cycle. Thanks for your time — happy to revisit next year."),
             ("call", "rep", "Left VM for {champ}, want to understand what it would take to win this back."),
         ]),
    dict(name="verbal_yes_then_lost", objection="none", action="confirm_procurement_timeline",
         stage="Negotiation", gap=(3, 10), inflated=False, weight=0.25, steps=[
             ("meeting", "rep", "Final review with {champ} and {econ}. No open questions."),
             ("email", "buyer", "We're going ahead with {product}. {econ} signed off; PO should be out next week."),
             ("call", "rep", "Confirmed PO is routing."),
         ]),
    dict(name="evaluating_open_lost", objection="competitor", action="run_competitive_bakeoff",
         stage="Proposal", gap=(4, 12), inflated=False, steps=[
             ("call", "rep", "Requirements call with {champ}."),
             ("email", "buyer", "We're evaluating {product} against {comp}; decision in about three weeks. "
                                "Could you get us a loaner unit for the lab?"),
             ("email", "rep", "Loaner request submitted."),
         ]),
    dict(name="no_authority", objection="authority", action="multithread_to_economic_buyer",
         stage="Proposal", gap=(12, 30), inflated=True, steps=[
             ("call", "rep", "{champ} loves the product and asked for a quote."),
             ("email", "buyer", "Thanks for the quote! I'll try to get time with {econ}. To be honest I "
                                "don't own this budget and she has other priorities this quarter."),
             ("email", "rep", "Checked in with {champ}. No update yet on {econ}'s availability."),
         ]),
]


def pick_archetype(won: bool, age_days: int):
    """Pick a story that fits inside the deal's real age (young deals can't be 'ghosted for 60 days')."""
    pool = WON if won else LOST
    fits = [a for a in pool if a["gap"][0] + len(a["steps"]) <= age_days]
    if not fits:
        return min(pool, key=lambda a: a["gap"][0] + len(a["steps"]))
    # Pure-noise stories (nothing in the record predicts the outcome) are kept rare.
    return rng.choices(fits, weights=[a.get("weight", 1.0) for a in fits])[0]


def spread_dates(start: pd.Timestamp, end: pd.Timestamp, n: int) -> list[pd.Timestamp]:
    """n dates in (start, end], sorted, roughly spread."""
    span = max((end - start).days, 1)
    if span >= n:
        offs = sorted(rng.sample(range(1, span + 1), n))
    else:  # very young deal: several touches can land on the same day
        offs = sorted(rng.choices(range(1, span + 1), k=n))
    return [start + timedelta(days=o) for o in offs]


def build():
    pipe = pd.read_csv(RAW / "sales_pipeline.csv", parse_dates=["engage_date", "close_date"])
    teams = pd.read_csv(RAW / "sales_teams.csv")
    accounts = pd.read_csv(RAW / "accounts.csv")
    products = pd.read_csv(RAW / "products.csv")

    pipe = pipe.merge(teams, on="sales_agent")
    open_deals = pipe[(pipe.engage_date < SOURCE_SNAPSHOT) & (pipe.close_date >= SOURCE_SNAPSHOT)
                      & (pipe.manager == MANAGER)].copy()
    open_deals = open_deals.sort_values("opportunity_id").reset_index(drop=True)

    # Price lookup that tolerates the real-data spelling drift ("GTXPro" vs "GTX Pro").
    price = {r.product: r.sales_price for r in products.itertuples()}
    price_norm = {k.replace(" ", "").lower(): v for k, v in price.items()}

    deals, contacts, activities, truth = [], [], [], []
    for d in open_deals.itertuples():
        won = d.deal_stage == "Won"
        engage = d.engage_date + SHIFT
        age = (DEMO_SNAPSHOT - engage).days
        arch = pick_archetype(won, age)
        champ, econ = person(), person()
        comp = rng.choice(COMPETITORS)
        list_price = price_norm[d.product.replace(" ", "").lower()]
        n_steps = len(arch["steps"])
        authors = [st[1] for st in arch["steps"]]
        last_buyer = max((i for i, a in enumerate(authors) if a == "buyer"), default=n_steps - 1)
        # The gap is days since the BUYER last touched the deal; rep voicemails after that
        # don't count. Leave room for every earlier activity after the engage date.
        gap = min(rng.randint(*arch["gap"]), max(age - (last_buyer + 1), 0))
        last_buyer_touch = DEMO_SNAPSHOT - timedelta(days=gap)
        dates = spread_dates(engage, last_buyer_touch, last_buyer + 1)
        dates[-1] = last_buyer_touch
        if last_buyer < n_steps - 1:
            dates += spread_dates(last_buyer_touch, DEMO_SNAPSHOT, n_steps - last_buyer - 1)
        dates = [min(d, DEMO_SNAPSHOT) for d in dates]

        fill = dict(champ=champ, econ=econ, comp=comp, product=d.product, rep=d.sales_agent,
                    account=d.account, price=f"${list_price:,.0f}")
        for i, (kind, author, text) in enumerate(arch["steps"]):
            activities.append(dict(
                activity_id=f"{d.opportunity_id}-{i+1}", opportunity_id=d.opportunity_id,
                date=dates[i].date(), type=kind,
                author={"rep": d.sales_agent, "buyer": champ, "auto": "system"}[author],
                text=text.format(**fill)))

        # ~20% of amounts left blank: reps don't always fill it in. Forces a price lookup.
        amount = "" if rng.random() < 0.2 else list_price
        deals.append(dict(
            opportunity_id=d.opportunity_id, account=d.account, product=d.product,
            sales_agent=d.sales_agent, stage=arch["stage"], amount=amount,
            created_date=engage.date(),
            expected_close=(DEMO_SNAPSHOT + timedelta(days=rng.randint(10, 75))).date(),
            primary_contact=champ, last_activity_date=dates[-1].date(),
            next_step=rng.choice(["Follow up", "Send proposal", "Check in with champion",
                                  "Schedule call", ""])))
        contacts.append(dict(opportunity_id=d.opportunity_id, name=champ,
                             title=rng.choice(CHAMP_TITLES), role="champion"))
        contacts.append(dict(opportunity_id=d.opportunity_id, name=econ,
                             title=rng.choice(ECON_TITLES), role="economic_buyer"))
        truth.append(dict(
            opportunity_id=d.opportunity_id, outcome=d.deal_stage,
            actual_close_date=(d.close_date + SHIFT).date(),
            actual_close_value=d.close_value if won else 0.0,
            list_price=list_price, archetype=arch["name"], objection=arch["objection"],
            correct_next_action=arch["action"], rep_stage_inflated=arch["inflated"],
            days_since_buyer_touch=gap, competitor=comp if arch["objection"] == "competitor" else ""))

    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(deals).to_csv(OUT / "deals.csv", index=False)
    pd.DataFrame(contacts).to_csv(OUT / "contacts.csv", index=False)
    pd.DataFrame(activities).sort_values(["opportunity_id", "date"]).to_csv(OUT / "activities.csv", index=False)
    pd.DataFrame(truth).to_csv(OUT / "ground_truth.csv", index=False)

    team = teams[teams.manager == MANAGER].copy()
    team.to_csv(OUT / "team.csv", index=False)
    products.to_csv(OUT / "products.csv", index=False)
    accounts[accounts.account.isin(open_deals.account)].to_csv(OUT / "accounts.csv", index=False)

    tdf = pd.DataFrame(truth)
    (OUT / "company.md").write_text(f"""# {COMPANY} — pipeline review brief

**Who we are.** {COMPANY} sells server and workstation hardware (GTX, MG and GTK product
lines) to mid-market and enterprise IT teams. Deals are typically single-product
purchases; list prices are in `products.csv`.

**As of:** {DEMO_SNAPSHOT.date()} (Monday). This is the weekly pipeline review for
{MANAGER}'s Central region team ({len(team)} reps, {len(deals)} open opportunities).

**What the manager wants to know.**
1. Which open deals should the team spend its time on this week, and why?
2. Which deals are at risk, and what did the *buyer* actually say?
3. For each prioritised deal: one specific next action.

**Data.** `deals.csv` is the CRM snapshot as the reps left it — stages are rep-set and
sometimes optimistic, and `amount` is blank where the rep didn't enter it.
`activities.csv` holds call notes, emails and meeting notes. `contacts.csv` lists the
champion and the economic buyer for each deal.

**Historical context.** Company-wide win rate on closed deals is about 63%. Won deals
take a median of 57 days from first engagement to close; lost deals go quiet earlier.
""")
    print(f"{len(deals)} deals, {len(activities)} activities -> {OUT}")
    print(tdf.groupby(["outcome", "archetype"]).size())
    print("pipeline at list price: ${:,.0f}; actually closed: ${:,.0f}".format(
        tdf.list_price.sum(), tdf.actual_close_value.sum()))


if __name__ == "__main__":
    build()

# Claim ledger — spec

Input: one opportunity and its activity record (date, type, author, text), with a speaker per
activity: buyer / rep / system / unknown (see attribution). PII is tokenised before the model
sees it.

The model fills a fixed schema of *buyer-stated* facts. Unknown = null; never inferred from
the rep or the CRM. Slots: budget_status {unknown, approved, constrained, frozen,
no_budget_owner}; decision_timeline (free text); decision_date (ISO); economic_buyer (name);
champion_status {unknown, active, left_company, no_authority}; competitor_status
{none_mentioned, evaluating, leaning_competitor, chose_competitor, chose_us}; competitor_name;
product_discussed; units_discussed (int); total_stated_usd (number); commitment {none,
verbal_yes, po_in_flight, signed, declined, paused}; last_buyer_promise (verbatim);
last_buyer_promise_date; rep_sentiment_after_last_buyer_message {n/a, positive, neutral,
negative}. Every non-null slot carries quotes[slot]: a verbatim sentence from the record.

Verifier (code): a slot whose quote is not found verbatim in a buyer/system activity — or
inside a quoted-buyer span of a rep note — is set to null and listed in `dropped`. Dates and
numbers ride on their parent slot's quote (decision_date ← decision_timeline,
last_buyer_promise_date ← last_buyer_promise, units/total ← product_discussed). Dates come from
the activity that contains the quote, not from the model; a decision_date more than 180 days
after its quote is dropped. Kept slots get an evidence grade: A (direction/address), B (author
is a contact), C (quoted inside a rep note).

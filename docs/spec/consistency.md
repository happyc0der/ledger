# Consistency — spec (ledger vs CRM, pure code)

Per deal, with as_of = review date and thresholds from Settings:
- M1 stage_vs_buyer: late stage (Proposal/Negotiation) and buyer said budget frozen / declined / paused / leaning to a competitor / chose a competitor.
- M2 contact_contradiction: champion left (auto-reply) but still primary; CRM economic buyer ≠ the person the buyer names (match on any shared name token); contact says they lack authority in a late stage.
- M3 expired_promise: buyer's last promise/callback older than promise_days (14) with no buyer message since, unless the buyer declined/paused.
- M4 timeline_contradiction: expected_close before the buyer's decision date; or budget frozen / paused with expected_close inside frozen_window_days (75). Skipped when the close date is already past (that is S1).
- M5 scope_vs_amount: buyer discussed N>1 units; CRM amount ≠ N × list price.
- M6 zombie: buyer chose a competitor; deal still open. A "competitor" that is one of our own products is not a competitor.
- M7 cross_deal_contact (per account): a contact reported gone on one deal is still primary on another.
- M8 happy_ears: rep note positive after the buyer paused/declined/leaned away.
- M9 missing_economic_buyer: late stage, no economic buyer contact in CRM.
- M10 arithmetic: buyer's stated total ≠ units × list price by more than 5%.
Every issue carries the CRM value, the buyer quote, the evidence grade (C lowers severity), and one action from a fixed menu. Each check also reports pass / fail / skipped with a reason.
Rules S1–S8 (fields only): past close date; no next step past Qualification; dormant > dormant_days; amount blank late; early stage older than stalled_multiplier × median cycle; duplicate (same account+product, created ≤10 days after a sibling, ≤1 activity, early stage); activity before creation; last_activity field older than newest activity.

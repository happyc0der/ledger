| | rules | v3 |
|---|---|---|
| findings | 68 | 139 |
| precision / recall (all) | 100% / 27% | 97% / 54% |
| syntactic S1–S8 recall | 99% | 99% |
| semantic M1–M10 recall | 0% | 37% |
| semantic precision | 0% | 94% |
| clean deals falsely flagged | 0/86 (0%) | 0/86 (0%) |

| type | rules P/R | v3 P/R |
|---|---|---|
| S1_past_close_date | 100% / 100% (12/12) | 100% / 100% (12/12) |
| S2_no_next_step | 100% / 100% (10/10) | 100% / 100% (10/10) |
| S3_dormant | 100% / 100% (8/8) | 100% / 100% (8/8) |
| S4_amount_blank_late | 100% / 100% (10/10) | 100% / 100% (10/10) |
| S5_stalled_early_stage | 100% / 100% (6/6) | 100% / 100% (6/6) |
| S6_duplicate_deal | 100% / 86% (6/7) | 100% / 86% (6/7) |
| S7_activity_before_creation | 100% / 100% (8/8) | 100% / 100% (8/8) |
| S8_last_activity_field_wrong | 100% / 100% (8/8) | 100% / 100% (8/8) |
| M1_stage_vs_buyer | 0% / 0% (0/29) | 100% / 14% (4/29) |
| M2_contact_contradiction | 0% / 0% (0/26) | 100% / 54% (14/26) |
| M3_expired_promise | 0% / 0% (0/43) | 79% / 35% (15/43) |
| M4_timeline_contradiction | 0% / 0% (0/13) | 100% / 23% (3/13) |
| M5_scope_vs_amount | 0% / 0% (0/4) | 100% / 75% (3/4) |
| M6_zombie | 0% / 0% (0/15) | 100% / 7% (1/15) |
| M7_cross_deal_contact | 0% / 0% (0/8) | 100% / 50% (4/8) |
| M8_happy_ears | 0% / 0% (0/14) | 0% / 0% (0/14) |
| M9_missing_economic_buyer | 0% / 0% (0/20) | 100% / 100% (20/20) |
| M10_arithmetic | 0% / 0% (0/7) | 100% / 43% (3/7) |
| metric | v1 | v3 |
|---|---|---|
| deals | 235 | 235 |
| coverage | 1.000 | 1.000 |
| phantom_deals | 0 | 0 |
| duplicate_deals | 0 | 0 |
| revenue_top20 | $73,345 | $80,746 |
| revenue_top20_oracle | $113,772 | $113,772 |
| revenue_top20_pct | 0.645 | 0.710 |
| brier | 0.133 | 0.127 |
| objection_acc | 0.677 | 0.949 |
| action_acc | 0.872 | 0.936 |
| generic_actions | 15 | 21 |
| fabrications | 6 | 0 |
| fab_amount | 1 | 0 |
| fab_gap | 5 | 0 |
| fab_quote | 0 | 0 |
| stated_pipeline | $663,655 | $654,013 |
| true_pipeline | $654,013 | $654,013 |
| pipeline_error_pct | 0.015 | 0.000 |

Reliability (v1): stated p bin → actual win rate
- (-0.001, 0.2]: n=64, stated=0.09, actual=0.08
- (0.2, 0.4]: n=11, stated=0.33, actual=0.45
- (0.4, 0.6]: n=28, stated=0.52, actual=0.68
- (0.6, 0.8]: n=64, stated=0.75, actual=0.97
- (0.8, 1.0]: n=68, stated=0.87, actual=0.78

Reliability (v3): stated p bin → actual win rate
- (-0.001, 0.2]: n=57, stated=0.1, actual=0.05
- (0.2, 0.4]: n=17, stated=0.29, actual=0.41
- (0.4, 0.6]: n=18, stated=0.48, actual=0.56
- (0.6, 0.8]: n=23, stated=0.75, actual=0.91
- (0.8, 1.0]: n=120, stated=0.89, actual=0.86
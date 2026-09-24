# Auditor — spec

Deterministic, no ground truth. Sources: PRISM traces export + trace detail (guardrail flags with
matched text), PRISM trajectories + rule evaluations, the agents' own run rows, the CRM.
Findings carry severity, source (data / agent / guardrail / instrumentation), evidence and a fix.
Checks: data hygiene (emails, phones, times, relatives in notes; names unknown to the CRM;
attribution coverage), catalogue spelling drift, output integrity (duplicates/phantoms/missing),
stated-vs-computed (day gaps, amounts, pipeline totals, quotes), evidence validity (every issue's
quote exists verbatim), generic actions, calibration smell, guardrail flags traced back to where
the matched text lives (source data / agent output / false positive), PRISM rule failures ≥20% per
agent, observed precision from manager reviews. The audit run is itself a PRISM trajectory.

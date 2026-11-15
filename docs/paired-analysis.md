# Family-paired analysis

`python -m chesslab.paired INPUT --output NEW_OUTPUT` reads JSON with `arms`
(ordered names) and `rows` (one per assigned unit). Each row has `unit`, `family`
and `values`, with an explicit finite number or null for every arm. Include every
assigned unit. The program cannot detect units omitted by the upstream exporter;
reconcile the input against the frozen collection schedule before analysis.

For a response-success endpoint, encode a missing, invalid or late answer as zero.
For engine quality, use null for an unavailable exact score. Preserve bound/mate
categories in the originating score artifacts; they are not invented centipawns.
Run each predeclared pair on its common scored units, and use an all-arm common
cohort as a coverage sensitivity analysis. Never interpret conditional quality
as an intent-to-treat improvement.

All contrasts in one invocation share the same complete-unit cohort and sampled
family indices. The estimate is the equal-weight mean of paired family means,
with 20,000 family bootstrap resamples at seed 2026111504. Output includes assigned,
available and common counts, missing units/families, every family difference,
percentile intervals, leave-one-family-out results and an exact sign-flip reference
for at most 16 families. The reference assumes exchangeability under sign reversal;
it is not a claim of randomized treatment effects or multiplicity-adjusted evidence.

With six families the uncertainty is unstable. Frames and positions from one
generated game are related observations. Bootstrap intervals do not calibrate
human rating, generalization to all openings, or native browser reliability.

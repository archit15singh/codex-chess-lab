# V2 family analysis

`chesslab.v2_analysis` applies the frozen mathematical rules to normalized,
all-assigned operational endpoints. It collects no observations and supplies no
chess advice. The caller must first verify raw provenance, actual model/tool use,
timing, termination, legality and reference coverage under the private protocol.
Passing a number to this module does not establish that it was independently
audited. Keep raw chess outcomes, missingness and unknown true-quality bounds in
separate tables; operational zero is not an invented board loss or true error.

Rows have exactly `unit`, `family` and `values`, with one value for every arm.
`family_summary` requires complete bounded operational values: it rejects `None`
instead of silently dropping an assigned unit. It computes each family's mean
over its units, then equally weights those family means. This preserves the
grouping when families have different numbers of observations.

```python
from fractions import Fraction
from chesslab.v2_analysis import bootstrap_plan, family_summary

rows = [
    {"unit": "one", "family": "a", "values": {"baseline": 0, "candidate": 1}},
    {"unit": "two", "family": "b", "values": {"baseline": 1, "candidate": 0}},
]
plan = bootstrap_plan(["a", "b"])
summary = family_summary(rows, ["baseline", "candidate"], plan=plan,
                         contrast_alpha=Fraction(1, 40))
```

The example is synthetic arithmetic, not a study result. The private V2 protocol
owns sample sizes, grouping, arms and inferential scope.

## Joint resampling and uncertainty

Generate and preserve one explicit family-name resampling plan. Reuse that plan
for all arms and fields of a comparison. Native setting/color vectors move
together. For the primary improvement cohort, pass the two declared family
strata to `bootstrap_plan`; `project_plan` retains the same first-stratum draws
for the shared reasoning baseline. A projection that changes replicate sample
size is rejected. The returned plan can be archived directly, making its actual
draws available for regeneration independent of a future random-library change.

The default is 4,000 replicates with seed 4815162342. Bands use sorted replicate
indices `floor((B-1)*.025)` and `ceil((B-1)*.975)` without interpolation: 99 and
3900 for the default. They are **descriptive percentile bands**, not validated
95% confidence intervals. Leave-one-family-out minimum and maximum estimates
and the exact family effects accompany every summary.

Hoeffding intervals are separate. They require independent bounded family
realizations conditional on the fixed benchmark/configuration. Fresh contexts
do not prove that assumption or make the positions a representative population.
Arm means receive pointwise alpha 1/20 bounds. The caller supplies contrast alpha;
1/40 gives the two preregistered primary contrasts their Bonferroni joint scope.
It does not establish simultaneous coverage for any larger set of contrasts.
Other contrasts remain exploratory. Exact sign counts reuse `grouped_reference`;
their causal/randomization interpretation still needs the actual design and
no-interference assumptions, rather than merely an arithmetic output.

## Diagnostic promotion

`promotion` requires the complete 48-unit, 24-family primary matrix, exactly two
units per family and binary integer audited credits in baseline/sham/candidate
order. It applies candidate-minus-baseline and candidate-minus-sham positive
inclusive family tails, with Holm at alpha 1/20 for exactly those two tests.
It also requires at least five additional candidate credits against each control,
candidate completion no more than two below baseline and actual-stop median
latency ratio candidate/baseline at most 5/4.

Supply all 48 actual host-stop-minus-query-start integer microsecond latencies
for each arm. Preserve an unavailable value as `None`; missing or negative
latencies leave the cost gate unresolved and fail promotion. The baseline median
must be positive. Even medians use the exact average of sorted indices 23/24,
and the 5/4 boundary is compared as rational arithmetic without rounding or
averaging paired ratios. No observation disappears from the denominator.

The return value exposes every gate and exact count. A rejection can be a valid
result. Passing this benchmark rule does not prove a heterogeneous expected
gain of at least .10, native playing improvement, a human rating or model-weight
training. Candidate selection and its freeze happen elsewhere, before final
outcomes; this function cannot select or revise a policy.

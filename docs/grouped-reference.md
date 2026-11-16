# Exact grouped references

`chesslab.grouped_reference.exact_reference(rows, arms)` extends exact inclusive
sign counts to larger family sets. It does not change the historical V1 helper.
Each row explicitly names its unique unit, source family and every arm's endpoint.
Use finite numbers or null; JSON decimals are parsed with `Decimal` by the CLI.
The default endpoint bounds are zero through one. Out-of-range values fail rather
than being clipped into apparently better performance.

```sh
python -m chesslab.grouped_reference private-endpoints.json --output unique-reference.json
```

The function first selects one common cohort across **all supplied arms**, averages
within each source family and weights families equally. It retains assigned and
available counts, unmatched units and families without common data. A null quality
measurement is unavailable, not a zero-quality response. All-assigned operational
credit must be defined separately upstream, including its explicit failure rule.

Rational differences become integer weights with a common denominator. Dynamic
programming counts both signs, including doubled zero ties and inclusive tails.
It records the exact numerator, denominator and probability as a fraction. The
state-count and exact-integer precision ceilings fail closed; the code never
substitutes rounded weights or an approximate p-value. Numeric and scale precision
is limited to 512 bits (JSON decimals also have bounded length/exponent), comfortably
above the small rational credit endpoints used here. `holm` applies step-down adjustment using
exact rational comparisons and explicit hypothesis IDs.

These are reference calculations, not an automatic causal interpretation. A
conditional randomization test requires the actual prospective family-bundle
label-swap design, fixed policies and no interference. Otherwise sign symmetry
must be justified. Rejection of a sharp no-effect null is not an exact confidence
interval for an arbitrary heterogeneous average effect. Report uncertainty and
assumptions separately; neither a nonsignificant reference nor a zero point
estimate establishes equivalence, a rating, or absence of improvement.

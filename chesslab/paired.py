"""Exploratory paired endpoints with the source family as the resampling unit."""
import argparse
from itertools import product
import json
from math import isfinite
from pathlib import Path
from random import Random
from statistics import mean


def quantile(values, probability):
    ordered = sorted(values)
    location = (len(ordered) - 1) * probability
    lower = int(location)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (location - lower)


def paired_summary(rows, arms, *, resamples=20_000, seed=2026111504):
    """Rows are assigned units, with explicit nulls for unavailable endpoints.

    Every row has exactly unit, family, values; values names every requested arm.
    Binary reliability endpoints should encode failures as zero upstream. Quality
    endpoints use null for unavailable scores, never zero. All-arm complete cases
    define one common cohort for all reported contrasts. Families have equal
    weight regardless of their number of common units. This is conditional quality
    analysis when any endpoint is missing, not an intent-to-treat quality estimate.
    """
    if (not isinstance(arms, list) or len(arms) < 2
            or any(not isinstance(a, str) or not a for a in arms)
            or len(set(arms)) != len(arms)):
        raise ValueError('expected distinct nonempty arm names')
    if type(resamples) is not int or resamples < 1 or type(seed) is not int:
        raise ValueError('expected positive resample count and integer seed')
    if not isinstance(rows, list) or not rows:
        raise ValueError('expected assigned rows, including failures')
    seen, families, matched = set(), {}, {}
    available = {arm: 0 for arm in arms}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'unit', 'family', 'values'}:
            raise ValueError('row requires unit, family, values')
        unit, family, values = row['unit'], row['family'], row['values']
        if (not isinstance(unit, str) or not unit or unit in seen
                or not isinstance(family, str) or not family):
            raise ValueError('expected unique units and nonempty family names')
        if not isinstance(values, dict) or set(values) != set(arms):
            raise ValueError('every assigned row must explicitly name every arm')
        for arm, value in values.items():
            if value is not None and (type(value) not in (int, float) or not isfinite(value)):
                raise ValueError('endpoint must be finite number or null')
            available[arm] += value is not None
        seen.add(unit)
        families.setdefault(family, []).append(unit)
        if all(values[arm] is not None for arm in arms):
            matched.setdefault(family, []).append(row)
    names = sorted(matched)
    family_means = {family: {arm: mean(r['values'][arm] for r in matched[family]) for arm in arms}
                    for family in names}
    rng = Random(seed)
    # Identical sampled family indices are used for every contrast.
    samples = [[rng.randrange(len(names)) for _ in names] for _ in range(resamples)] if names else []
    contrasts = []
    for left_index, left in enumerate(arms):
        for right in arms[left_index + 1:]:
            differences = [family_means[f][right] - family_means[f][left] for f in names]
            if any(not isfinite(d) for d in differences):
                raise ValueError('paired difference overflow')
            estimate = mean(differences) if names else None
            bootstrap = [mean(differences[i] for i in indices) for indices in samples]
            # Exact small-cluster sign-flip reference; no multiple-testing claim.
            sign_flip = None
            if 0 < len(names) <= 16:
                outcomes = [abs(mean(d * s for d, s in zip(differences, signs)))
                            for signs in product((-1, 1), repeat=len(names))]
                sign_flip = {'assignments': len(outcomes),
                             'two_sided_p': sum(v >= abs(estimate) for v in outcomes) / len(outcomes),
                             'assumption': 'family differences exchangeable under sign reversal; exploratory reference only'}
            contrasts.append({'left': left, 'right': right, 'direction': 'right minus left',
                              'estimate': estimate,
                              'family_differences': dict(zip(names, differences)),
                              'bootstrap_percentile95': [quantile(bootstrap, .025), quantile(bootstrap, .975)] if bootstrap else None,
                              'leave_one_family_out': {f: mean(differences[:i] + differences[i+1:]) if len(names) > 1 else None
                                                       for i, f in enumerate(names)},
                              'sign_flip_reference': sign_flip})
    return {'assigned_units': len(rows), 'assigned_families': len(families),
            'available_units_by_arm': available,
            'common_units': sum(map(len, matched.values())), 'common_families': len(names),
            'unmatched_units': [r['unit'] for r in rows if any(r['values'][a] is None for a in arms)],
            'families_without_common_units': sorted(set(families) - set(names)),
            'family_means': family_means, 'contrasts': contrasts,
            'bootstrap': {'seed': seed, 'resamples': resamples, 'unit': 'source family',
                          'weighting': 'equal family means, common units across supplied arms',
                          'coverage': 'conditional on complete cases; unavailable endpoints are not imputed',
                          'interval': 'exploratory percentile interval; six clusters give unstable uncertainty'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON with rows and ordered arms')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    value = json.loads(args.input.read_text())
    result = paired_summary(value['rows'], value['arms'])
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()

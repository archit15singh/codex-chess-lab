"""Exact inclusive sign-flip references for declared, bounded family endpoints.

This counts signs with integer dynamic programming, without floating tails or
enumerating every assignment. Interpretation depends on the frozen design:
conditional randomization requires its actual label-swap design and no
interference; otherwise sign symmetry is an assumption, not a proven property.
"""
import argparse
from decimal import Decimal
from fractions import Fraction
from itertools import combinations
import json
from math import isfinite, lcm
from pathlib import Path


def rational(value):
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, Decimal) and value.is_finite():
        parts = value.as_tuple()
        if len(parts.digits) > 150 or abs(parts.exponent) > 150:
            raise ValueError('exact numeric precision limit exceeded; no rounding')
        result = Fraction(value)
    elif type(value) is int:
        result = Fraction(value)
    elif type(value) is float and isfinite(value):
        result = Fraction(str(value))
    else:
        raise ValueError('finite numeric endpoint required; parse JSON decimals exactly')
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > 512:
        raise ValueError('exact numeric precision limit exceeded; no rounding')
    return result


def sign_counts(differences, *, state_limit=100_000):
    if (not isinstance(differences, (list, tuple)) or not differences
            or type(state_limit) is not int or state_limit < 1
            or len(differences) > 64):
        raise ValueError('one through 64 families and a positive state limit required')
    values = [rational(value) for value in differences]
    scale = 1
    for value in values:
        scale = lcm(scale, value.denominator)
        if scale.bit_length() > 512:
            raise ValueError('exact scale precision limit exceeded; no rounding')
    weights = [int(value * scale) for value in values]
    distribution = {0: 1}
    for weight in weights:
        following = {}
        for total, count in distribution.items():
            for next_total in (total - weight, total + weight):
                following[next_total] = following.get(next_total, 0) + count
                if len(following) > state_limit:
                    raise ValueError('exact state limit exceeded; never round or silently approximate')
        distribution = following
    observed = sum(weights)
    assignments = 2 ** len(values)
    assert sum(distribution.values()) == assignments
    positive = sum(count for total, count in distribution.items() if total >= observed)
    negative = sum(count for total, count in distribution.items() if total <= observed)
    two_sided = sum(count for total, count in distribution.items() if abs(total) >= abs(observed))
    return {'families': len(values), 'assignments': assignments, 'states': len(distribution),
            'positive_inclusive_tail': positive, 'negative_inclusive_tail': negative,
            'two_sided_inclusive_tail': two_sided,
            'positive_p_exact': str(Fraction(positive, assignments)),
            'negative_p_exact': str(Fraction(negative, assignments)),
            'two_sided_p_exact': str(Fraction(two_sided, assignments))}


def exact_reference(rows, arms, *, bounds=(0, 1), state_limit=100_000):
    if (not isinstance(arms, list) or len(arms) < 2
            or any(not isinstance(arm, str) or not arm for arm in arms)
            or len(set(arms)) != len(arms)):
        raise ValueError('distinct nonempty arm names required')
    if not isinstance(rows, list) or not rows:
        raise ValueError('all assigned rows, including unavailable endpoints, required')
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
        raise ValueError('explicit endpoint bounds required')
    low, high = map(rational, bounds)
    if low >= high:
        raise ValueError('ordered finite endpoint bounds required')
    seen, assigned, matched = set(), {}, {}
    available = dict.fromkeys(arms, 0)
    unmatched = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'unit', 'family', 'values'}:
            raise ValueError('row requires exactly unit, family and values')
        unit, family, values = row['unit'], row['family'], row['values']
        if (not isinstance(unit, str) or not unit or unit in seen
                or not isinstance(family, str) or not family
                or not isinstance(values, dict) or set(values) != set(arms)):
            raise ValueError('unique units, family and every declared arm required')
        seen.add(unit)
        assigned.setdefault(family, []).append(unit)
        parsed = {}
        for arm in arms:
            value = None if values[arm] is None else rational(values[arm])
            if value is not None and not low <= value <= high:
                raise ValueError('endpoint outside declared bounds; no clipping permitted')
            parsed[arm] = value
            available[arm] += value is not None
        if all(value is not None for value in parsed.values()):
            matched.setdefault(family, []).append(parsed)
        else:
            unmatched.append(unit)
    names = sorted(matched)
    means = {family: {arm: sum((row[arm] for row in matched[family]), Fraction())
                          / len(matched[family]) for arm in arms} for family in names}
    contrasts = []
    for left, right in combinations(arms, 2):
        differences = {family: means[family][right] - means[family][left] for family in names}
        estimate = sum(differences.values(), Fraction()) / len(names) if names else None
        contrasts.append({'left': left, 'right': right, 'direction': 'right minus left',
            'estimate_exact': str(estimate) if estimate is not None else None,
            'family_differences_exact': {family: str(value) for family, value in differences.items()},
            'sign_flip': sign_counts(list(differences.values()), state_limit=state_limit) if names else None})
    return {'assigned_units': len(rows), 'assigned_families': len(assigned),
            'available_units_by_arm': available, 'common_units': sum(map(len, matched.values())),
            'common_families': len(names), 'unmatched_units': unmatched,
            'families_without_common_units': sorted(set(assigned) - set(names)),
            'family_means_exact': {family: {arm: str(value) for arm, value in values.items()}
                                   for family, values in means.items()},
            'contrasts': contrasts,
            'interpretation': 'Exact inclusive sign counts only. Conditional randomization or symmetry assumptions must be justified separately. No confidence interval, rating or equivalence claim.'}


def holm(references, *, alpha=Fraction(1, 20)):
    alpha = rational(alpha)
    if not 0 < alpha < 1 or not isinstance(references, list) or not references:
        raise ValueError('nonempty references and alpha between 0 and 1 required')
    seen, ordered = set(), []
    for reference in references:
        if not isinstance(reference, dict) or set(reference) != {'id', 'tail', 'assignments'}:
            raise ValueError('reference requires id, tail and assignments')
        identity, tail, total = reference['id'], reference['tail'], reference['assignments']
        if (not isinstance(identity, str) or not identity or identity in seen
                or type(tail) is not int or type(total) is not int or not 0 <= tail <= total or total < 1):
            raise ValueError('unique reference and valid exact counts required')
        seen.add(identity)
        ordered.append((Fraction(tail, total), identity))
    ordered.sort()
    adjusted, continuing, results = Fraction(), True, []
    for index, (probability, identity) in enumerate(ordered):
        remaining = len(ordered) - index
        adjusted = min(Fraction(1), max(adjusted, probability * remaining))
        continuing = continuing and probability <= alpha / remaining
        results.append({'id': identity, 'p_exact': str(probability),
                        'adjusted_p_exact': str(adjusted), 'threshold_exact': str(alpha / remaining),
                        'reject': continuing})
    return {'alpha_exact': str(alpha), 'method': 'Holm step-down; exact rational comparisons', 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    value = json.loads(args.input.read_text(), parse_float=Decimal)
    result = exact_reference(value['rows'], value['arms'], bounds=value.get('bounds', [0, 1]))
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()

"""Frozen-design family summaries and diagnostic promotion arithmetic.

Inputs are all-assigned, audited operational endpoints, not raw answers. This
module cannot verify provenance, blindness, clocks, legal moves or model traces.
It never launches a subject, chooses a policy or interprets engine strength as
human Elo. Descriptive bootstrap bands and assumption-dependent Hoeffding bounds
are deliberately distinct from the exact sharp-null promotion references.
"""
from fractions import Fraction
from math import ceil, floor, log, sqrt
import random

from .grouped_reference import exact_reference, holm, rational


def bootstrap_plan(families, *, strata=None, resamples=4000, seed=4815162342):
    """Sample whole family names, preserving joint arm/item vectors and strata.

    Reuse this returned plan across linked analyses. Projecting a stratified
    primary plan onto its first stratum preserves the shared reasoning cohort.
    """
    if (not isinstance(families, list) or not families or len(families) > 64
            or any(not isinstance(f, str) or not f for f in families)
            or len(set(families)) != len(families)
            or type(resamples) is not int or not 2 <= resamples <= 100_000
            or type(seed) is not int):
        raise ValueError('distinct family names, bounded resample count and integer seed required')
    groups = [sorted(families)] if strata is None else strata
    if (not isinstance(groups, list) or not groups
            or any(not isinstance(g, list) or not g for g in groups)):
        raise ValueError('nonempty strata required')
    flat = [f for group in groups for f in group]
    if (any(not isinstance(f, str) for f in flat)
            or len(flat) != len(families) or set(flat) != set(families)):
        raise ValueError('strata must partition families exactly once')
    rng = random.Random(seed)
    return [[rng.choice(sorted(group)) for group in groups for _ in group]
            for _ in range(resamples)]


def project_plan(plan, families):
    """Project a shared plan only if every draw retains the full target size."""
    if not isinstance(families, list) or not families or len(set(families)) != len(families):
        raise ValueError('distinct projected families required')
    if not isinstance(plan, list) or len(plan) < 2:
        raise ValueError('at least two bootstrap draws required')
    result = []
    for draw in plan:
        if not isinstance(draw, list):
            raise ValueError('family-name draws required')
        projected = [name for name in draw if name in families]
        if len(projected) != len(families):
            raise ValueError('projection changes sample size; use the declared strata')
        result.append(projected)
    return result


def hoeffding(estimate, families, *, bounds=(0, 1), alpha=Fraction(1, 20)):
    estimate, alpha = rational(estimate), rational(alpha)
    if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
        raise ValueError('explicit endpoint bounds required')
    low, high = map(rational, bounds)
    if (type(families) is not int or not 1 <= families <= 64
            or not low < high or not low <= estimate <= high or not 0 < alpha < 1):
        raise ValueError('bounded estimate, family count and probability required')
    radius = float(high - low) * sqrt(log(2 / float(alpha)) / (2 * families))
    return {'estimate_exact': str(estimate), 'families': families, 'alpha_exact': str(alpha),
            'radius': radius, 'lower': max(float(low), float(estimate) - radius),
            'upper': min(float(high), float(estimate) + radius),
            'label': 'Assumption-dependent independent bounded-family Hoeffding interval',
            'assumption': 'Independent family realizations conditional on fixed benchmark and configurations; not verified host independence or population representativeness.'}


def family_summary(rows, arms, *, plan, contrast_alpha=Fraction(1, 20)):
    """Summarize complete operational credit rows; never drop unavailable rows.

    Each row has unit, family and values for every arm, all within[0,1]. Supply
    zero only under the protocol's audited operational predicate. Unknown true
    quality/outcome bounds require a separate table and are not imputed here.
    Pass alpha1/40 for the two primary contrast intervals; alpha1/20 is pointwise.
    """
    exact = exact_reference(rows, arms)
    if exact['unmatched_units']:
        raise ValueError('operational endpoints must cover every assigned unit and arm')
    means = {f: {arm: Fraction(value) for arm, value in values.items()}
             for f, values in exact['family_means_exact'].items()}
    names = sorted(means)
    if not isinstance(plan, list) or len(plan) < 2:
        raise ValueError('explicit joint bootstrap plan required')
    for draw in plan:
        if (not isinstance(draw, list) or len(draw) != len(names)
                or any(not isinstance(f, str) or f not in means for f in draw)):
            raise ValueError('each draw must contain the declared number of valid families')
    n, count = len(names), len(plan)
    lower_index, upper_index = floor((count - 1) * .025), ceil((count - 1) * .975)

    def summarize(values, bounds, alpha):
        point = sum(values.values(), Fraction()) / n
        replicates = sorted(sum((values[f] for f in draw), Fraction()) / n for draw in plan)
        leave_one = [(sum(values.values(), Fraction()) - values[f]) / (n - 1)
                     for f in names] if n > 1 else []
        return {'estimate_exact': str(point), 'family_values_exact': {f: str(values[f]) for f in names},
                'hoeffding': hoeffding(point, n, bounds=bounds, alpha=alpha),
                'bootstrap': {'label': 'Descriptive family-bootstrap percentile band; not a validated95% confidence interval',
                              'replicates': count, 'lower_index': lower_index, 'upper_index': upper_index,
                              'lower_exact': str(replicates[lower_index]), 'upper_exact': str(replicates[upper_index])},
                'leave_one_family_out': {'minimum_exact': str(min(leave_one)) if leave_one else None,
                                         'maximum_exact': str(max(leave_one)) if leave_one else None}}

    arm_results = {arm: summarize({f: means[f][arm] for f in names}, (0, 1), Fraction(1, 20))
                   for arm in arms}
    contrasts = []
    for contrast in exact['contrasts']:
        values = {f: Fraction(value) for f, value in contrast['family_differences_exact'].items()}
        contrasts.append(dict(left=contrast['left'], right=contrast['right'],
                              **summarize(values, (-1, 1), contrast_alpha),
                              sign_flip=contrast['sign_flip']))
    return {'assigned_units': len(rows), 'families': n, 'arms': arm_results, 'contrasts': contrasts,
            'grouping': 'Equal family means after within-family unit means; every arm shares the supplied resampling vectors.',
            'inference_limit': exact['interpretation']}


def promotion(rows, *, completions, latency_us):
    """Apply the fixed48unit/24family two-control diagnostic promotion rule.

    All supplied values must be audited binary verified credits. Completion
    counts come from the separately audited predicate. Latencies are all48
    actual host-stop-minus-query-start integer microseconds per arm, or None if
    unverified. Missing/negative stops never disappear from the cost denominator.
    """
    arms = ['baseline', 'sham', 'candidate']
    result = exact_reference(rows, arms)
    if (len(rows) != 48 or result['assigned_families'] != 24
            or result['unmatched_units']):
        raise ValueError('complete48unit/24family operational primary matrix required')
    counts = {}
    for row in rows:
        counts[row['family']] = counts.get(row['family'], 0) + 1
        if any(type(v) is not int or v not in (0, 1) for v in row['values'].values()):
            raise ValueError('audited primary credits must be binary integers')
    if set(counts.values()) != {2}:
        raise ValueError('exactly two matched units per primary family required')
    if (not isinstance(completions, dict) or set(completions) != set(arms)
            or any(type(v) is not int or not 0 <= v <= 48 for v in completions.values())):
        raise ValueError('all48assigned completion counts required')
    if not isinstance(latency_us, dict) or set(latency_us) != set(arms):
        raise ValueError('all three assigned latency vectors required')
    cost_reasons, medians = [], {}
    for arm in arms:
        vector = latency_us[arm]
        if not isinstance(vector, list) or len(vector) != 48:
            raise ValueError('all48assigned latencies required; never omit missing stops')
        if any(v is not None and type(v) is not int for v in vector):
            raise ValueError('integer microseconds or None required')
        if any(v is None or v < 0 for v in vector):
            cost_reasons.append(arm + ': missing or invalid actual stop latency')
            medians[arm] = None
        else:
            values = sorted(vector)
            medians[arm] = Fraction(values[23] + values[24], 2)
    if medians['baseline'] == 0:
        cost_reasons.append('baseline median must be positive')
    cost_resolved = not cost_reasons
    cost_pass = cost_resolved and 4 * medians['candidate'] <= 5 * medians['baseline']
    credits = {arm: sum(r['values'][arm] for r in rows) for arm in arms}
    gains = {control: 10 * (credits['candidate'] - credits[control]) >= 48
             for control in ('baseline', 'sham')}
    references = []
    for contrast in result['contrasts']:
        if contrast['right'] == 'candidate':
            ref = contrast['sign_flip']
            references.append({'id': 'candidate-minus-' + contrast['left'],
                               'tail': ref['positive_inclusive_tail'], 'assignments': ref['assignments']})
    adjusted = holm(references)
    uncertainty = all(r['reject'] for r in adjusted['results'])
    completion_pass = completions['candidate'] >= completions['baseline'] - 2
    promoted = all(gains.values()) and uncertainty and completion_pass and cost_pass
    return {'decision': 'PROMOTE' if promoted else 'REJECT', 'scope': 'Diagnostic benchmark policy only; no native playing gain or expected minimum gain established.',
            'verified_credits': credits, 'minimum_observed_gain_pass': gains, 'holm': adjusted,
            'uncertainty_pass': uncertainty, 'completion_pass': completion_pass,
            'completions': completions, 'cost_resolved': cost_resolved, 'cost_pass': cost_pass,
            'cost_reasons': cost_reasons,
            'median_latency_us_exact': {a: str(v) if v is not None else None for a, v in medians.items()},
            'candidate_baseline_median_ratio_exact': str(medians['candidate'] / medians['baseline']) if cost_resolved else None,
            'provenance_limit': 'Arithmetic on supplied audited endpoints; this function does not audit raw observations or establish randomization assumptions.'}

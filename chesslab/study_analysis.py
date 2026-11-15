"""Predeclared static contrasts over an explicit nine-arm endpoint matrix.

The caller reconciles assigned rows with audited records first. Binary failure
endpoints use zero; unavailable quality uses null. This module selects no data,
answers, lessons, thresholds, or winning endpoint from observed effects.
"""
import argparse
import json
from pathlib import Path

from .paired import paired_summary

ARMS = list('ABCDEFGHI')
CONTRASTS = {
    'occupancy': ('A', 'B'),
    'legality_image': ('A', 'C'),
    'state_plus_legality': ('A', 'D'),
    'legality_with_state': ('B', 'D'),
    'state_with_legality': ('C', 'D'),
    'effort_high_minus_low': ('E', 'D'),
    'adaptive_minus_high': ('D', 'F'),
    'adaptive_minus_low': ('E', 'F'),
    'bounded_search': ('D', 'G'),
    'reflection': ('A', 'H'),
    'lesson_content': ('I', 'H'),
    'sham_context': ('A', 'I'),
}


def static_contrasts(rows, *, resamples=20_000, seed=2026111504):
    # Validate the full matrix, including unused cells, before projecting pairs.
    # One resample suffices for validation; reported estimates below use the
    # requested full budget. The validator also rejects omitted arm keys.
    coverage = paired_summary(rows, ARMS, resamples=1, seed=seed)
    main, sensitivity = {}, {}
    for name, arms in CONTRASTS.items():
        pair_rows, common_rows = [], []
        for row in rows:
            identity = {'unit': row['unit'], 'family': row['family']}
            complete = all(row['values'][arm] is not None for arm in ARMS)
            pair_rows.append({**identity, 'values': {a: row['values'][a] for a in arms}})
            common_rows.append({**identity, 'values': {a: row['values'][a] if complete else None for a in arms}})
        main[name] = paired_summary(pair_rows, list(arms), resamples=resamples, seed=seed)
        sensitivity[name] = paired_summary(common_rows, list(arms), resamples=resamples, seed=seed)
    interaction_rows = []
    for row in rows:
        values = row['values']
        without = values['B'] - values['A'] if values['B'] is not None and values['A'] is not None else None
        with_legality = values['D'] - values['C'] if values['D'] is not None and values['C'] is not None else None
        interaction_rows.append({'unit': row['unit'], 'family': row['family'],
                                 'values': {'state_without_legality': without,
                                            'state_with_legality': with_legality}})
    interaction = paired_summary(interaction_rows,
        ['state_without_legality', 'state_with_legality'], resamples=resamples, seed=seed)
    return {'schema_version': 1,
            'directions': 'Every pair is treatment minus control; interaction is D-B-C+A. Interpret endpoint units separately.',
            'coverage': {k: coverage[k] for k in ('assigned_units', 'assigned_families',
                'available_units_by_arm', 'common_units', 'common_families',
                'unmatched_units', 'families_without_common_units')},
            'main_pairwise_cohorts': main, 'all_arm_complete_sensitivity': sensitivity,
            'factorial_interaction': interaction,
            'limits': ['Assigned-row completeness requires external frozen-schedule reconciliation.',
                       'Each quality contrast conditions on explicit common available scores; no null-to-zero imputation.',
                       'Shared seed and identical retained family lists share sampled family indices; differing coverage is explicit.',
                       'Exploratory small-cluster estimates; no multiplicity-adjusted, rating, or model-training claim.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON containing rows with all nine arm values')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = static_contrasts(json.loads(args.input.read_text())['rows'])
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()

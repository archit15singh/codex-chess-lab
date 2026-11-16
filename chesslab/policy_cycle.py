"""Seal bounded policies and select once from complete development observations.

This records a procedural boundary. It does not launch actors, reserve budgets,
verify evaluator truth, prove blindness or decide promotion from final results.
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

RULE = 'maximum equal-family mean verified credit; ties use candidate order'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _hash(value):
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
        raise ValueError('a lowercase SHA256 digest is required')


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('nonempty text required')


def _keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError('unexpected fields; expected ' + names)


def _names(values):
    if not isinstance(values, list) or not values:
        raise ValueError('nonempty list of distinct names required')
    for value in values:
        _text(value)
    if len(set(values)) != len(values):
        raise ValueError('duplicate names')


def validate_plan(plan):
    _keys(plan, 'cycle_id protocol_sha256 final_manifest_sha256 training_families '
          'development_units final_families training_findings baseline sham candidates')
    _text(plan['cycle_id'])
    _hash(plan['protocol_sha256'])
    _hash(plan['final_manifest_sha256'])
    _names(plan['training_families'])
    _names(plan['final_families'])
    units = plan['development_units']
    if not isinstance(units, list) or not units:
        raise ValueError('development assignments required')
    for unit in units:
        _keys(unit, 'unit family')
        _text(unit['unit'])
        _text(unit['family'])
    _names([unit['unit'] for unit in units])
    groups = [set(plan['training_families']), {u['family'] for u in units},
              set(plan['final_families'])]
    if any(groups[i] & groups[j] for i in range(3) for j in range(i)):
        raise ValueError('training, development and final family labels overlap')
    findings = plan['training_findings']
    if not isinstance(findings, list) or not findings:
        raise ValueError('classified training evidence required')
    for finding in findings:
        _keys(finding, 'family category evidence_sha256')
        if finding['family'] not in groups[0]:
            raise ValueError('finding outside declared training families')
        _text(finding['category'])
        _hash(finding['evidence_sha256'])
    for name in ('baseline', 'sham'):
        _keys(plan[name], 'id prompt')
        if plan[name]['id'] != name:
            raise ValueError('control IDs must be baseline and sham')
        _text(plan[name]['prompt'])
    candidates = plan['candidates']
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 3:
        raise ValueError('one through three policies, including revisions, required')
    for candidate in candidates:
        _keys(candidate, 'id prompt mechanism training_finding_indices')
        for name in ('id', 'prompt', 'mechanism'):
            _text(candidate[name])
        indices = candidate['training_finding_indices']
        if (not isinstance(indices, list) or not indices
                or any(type(i) is not int or not 0 <= i < len(findings) for i in indices)
                or len(set(indices)) != len(indices)):
            raise ValueError('candidate must cite distinct training findings')
    policies = [plan['baseline'], plan['sham'], *candidates]
    _names([p['id'] for p in policies])
    _names([p['prompt'] for p in policies])
    return policies


def _write(path, value):
    # Exclusive output: never replace an earlier freeze or selection.
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(raw)
    return digest(raw)


def seal(path, plan):
    validate_plan(plan)
    return _write(path, {'schema_version': 1,
        'frozen_at': datetime.now(timezone.utc).isoformat(), 'plan': plan,
        'selection_rule': RULE})


def choose(plan, observations):
    """Pure development selection. Missing answers remain explicit zero-credit rows."""
    policies = validate_plan(plan)
    arms = [p['id'] for p in policies]
    assigned = {unit['unit']: unit['family'] for unit in plan['development_units']}
    expected = {(unit, arm) for unit in assigned for arm in arms}
    if not isinstance(observations, list):
        raise ValueError('complete development observations required')
    seen, credits, references = set(), {}, {}
    for row in observations:
        _keys(row, 'unit arm received on_time format_valid legal reference_available '
              'best_agreement source_sha256')
        _text(row['unit'])
        _text(row['arm'])
        key = row['unit'], row['arm']
        if key not in expected or key in seen:
            raise ValueError('duplicate or unassigned development observation')
        seen.add(key)
        _hash(row['source_sha256'])
        for name in ('received', 'on_time', 'format_valid', 'legal', 'reference_available'):
            if type(row[name]) is not bool:
                raise ValueError('observation flags must be booleans')
        references.setdefault(row['unit'], set()).add(row['reference_available'])
        if (not row['received'] and any(row[n] for n in ('on_time', 'format_valid', 'legal'))
                or not row['format_valid'] and row['legal']):
            raise ValueError('inconsistent response flags')
        comparable = row['legal'] and row['reference_available']
        if ((comparable and type(row['best_agreement']) is not bool)
                or (not comparable and row['best_agreement'] is not None)):
            raise ValueError('agreement must be unknown unless legal and reference available')
        credits[key] = int(row['received'] and row['on_time'] and row['format_valid']
                           and row['legal'] and row['best_agreement'] is True)
    if seen != expected:
        raise ValueError('every assigned arm/unit requires a row, including failures')
    if any(len(values) != 1 for values in references.values()):
        raise ValueError('common reference availability must match across all arms')
    families = sorted(set(assigned.values()))
    means = {arm: {family: sum(Fraction(credits[unit, arm]) for unit in assigned
                              if assigned[unit] == family)
                         / sum(f == family for f in assigned.values())
                   for family in families} for arm in arms}
    scores = {arm: sum(means[arm].values(), Fraction()) / len(families) for arm in arms}
    # max returns the first candidate on exact ties. Controls never select policy.
    winner = max(plan['candidates'], key=lambda policy: scores[policy['id']])
    return {'selected_id': winner['id'], 'selected_prompt': winner['prompt'],
            'selected_prompt_sha256': digest(winner['prompt'].encode()),
            'family_means_exact': {arm: {f: str(v) for f, v in values.items()}
                                   for arm, values in means.items()},
            'scores_exact': {arm: str(value) for arm, value in scores.items()},
            'assigned_observations': len(expected), 'families': len(families),
            'promotion': 'not evaluated; selected policy still requires untouched final test'}


def select(plan_path, development_path):
    plan_raw = Path(plan_path).read_bytes()
    envelope = json.loads(plan_raw)
    _keys(envelope, 'schema_version frozen_at plan selection_rule')
    if type(envelope['schema_version']) is not int or envelope['schema_version'] != 1:
        raise ValueError('unsupported plan schema')
    if envelope['selection_rule'] != RULE:
        raise ValueError('unsupported selection rule')
    development_raw = Path(development_path).read_bytes()
    development = json.loads(development_raw)
    _keys(development, 'phase plan_sha256 observations')
    if development['phase'] != 'development' or development['plan_sha256'] != digest(plan_raw):
        raise ValueError('requires development rows bound to this exact sealed plan')
    result = choose(envelope['plan'], development['observations'])
    # One selection destination per original plan, even if callers try new names.
    return _write(str(plan_path) + '.selection.json', {'schema_version': 1,
        'selected_at': datetime.now(timezone.utc).isoformat(),
        'plan_sha256': digest(plan_raw), 'development_sha256': digest(development_raw),
        'sealed_plan': envelope, 'development': development, 'selection': result})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seal', 'select'])
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--output', type=Path, help='seal only; select uses PLAN.selection.json')
    args = parser.parse_args()
    if args.action == 'seal':
        if args.output is None or args.development is not None:
            parser.error('seal requires --output and no --development')
        value = seal(args.output, json.loads(args.plan.read_text()))
    else:
        if args.development is None or args.output is not None:
            parser.error('select requires --development and no --output')
        value = select(args.plan, args.development)
    print(json.dumps({'output_sha256': value}))


if __name__ == '__main__':
    main()

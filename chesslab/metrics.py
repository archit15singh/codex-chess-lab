"""Offline per-game metrics; no strength inference or player-facing advice."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from math import isfinite
from pathlib import Path
from statistics import mean, median

from .stats import summarize


def seconds(start, end):
    if start is None or end is None:
        return None
    a, b = (datetime.fromisoformat(value.replace('Z', '+00:00')) for value in (start, end))
    if a.tzinfo is None or b.tzinfo is None:
        raise ValueError('timestamps require timezone')
    duration = (b - a).total_seconds()
    if duration < 0:
        raise ValueError('negative timing interval')
    return duration


def distribution(values):
    known = [value for value in values if value is not None]
    return {'measured': len(known), 'missing': len(values) - len(known),
            'median_seconds': median(known) if known else None,
            'mean_seconds': mean(known) if known else None,
            'max_seconds': max(known) if known else None}


def game_metrics(run, evaluation, *, actor):
    if actor not in {'white', 'black'}:
        raise ValueError('actor color must come from independent board audit')
    endpoint = summarize([run])
    intents, verifications = {}, {}
    for event in run['events']:
        payload = event['payload']
        if event['kind'] == 'intent':
            action = payload['action_id']
            if action in intents:
                raise ValueError('duplicate action intent')
            intents[action] = event
        elif event['kind'] == 'verification':
            action = payload['action_id']
            if action not in intents:
                raise ValueError('verification without preceding intent')
            if verifications.get(action, {}).get('payload', {}).get('outcome') in {'executed', 'not_executed'}:
                raise ValueError('verification after conclusive resolution')
            if payload['outcome'] not in {'executed', 'not_executed', 'uncertain'}:
                raise ValueError('unknown verification outcome')
            verifications[action] = event
    outcomes = Counter(verifications.get(action, {}).get('payload', {}).get('outcome', 'unverified')
                       for action in intents)
    executed = [event['payload']['move'] for action, event in intents.items()
                if verifications.get(action, {}).get('payload', {}).get('outcome') == 'executed']
    analysis = evaluation.get('engine_analysis', {})
    rows = analysis.get('rows')
    if rows is None:
        raise ValueError('engine analysis is required for move-quality metrics')
    actor_rows = [row for row in rows if row['turn'] == actor]
    if [row['move'] for row in actor_rows] != executed:
        raise ValueError('executed move sequence differs from actor-side evaluator sequence')
    losses = []
    missing = Counter()
    inversions = 0
    for row in actor_rows:
        scores = [row['best'], row['selected']]
        if any(s.get('mate') is not None for s in scores):
            missing['mate_score'] += 1
        elif any(s.get(flag) for s in scores for flag in ('lowerbound', 'upperbound')):
            missing['bounded_score'] += 1
        elif any(s.get('cp') is None for s in scores):
            missing['missing_score'] += 1
        else:
            values = [s['cp'] for s in scores]
            if any(type(value) not in {int, float} or not isfinite(value) for value in values):
                raise ValueError('invalid centipawn value')
            delta = values[0] - values[1]
            if row.get('cp_loss_raw') != delta:
                raise ValueError('stored score difference disagrees with scores')
            losses.append(delta)
            inversions += delta < 0
    decisions, resolutions = [], []
    for action, event in intents.items():
        decisions.append(seconds(event['payload'].get('decision_observed_at'), event['created']))
        verification = verifications.get(action)
        resolutions.append(seconds(event['created'], verification['created'])
                           if verification and verification['payload']['outcome'] != 'uncertain' else None)
    return {'schema_version': 1, 'run': run['run'], 'config': run['config'], 'actor': actor,
            'endpoint': endpoint, 'attempted': len(intents),
            'latest_verification_counts': dict(outcomes),
            'unresolved': outcomes['uncertain'] + outcomes['unverified'],
            'executed_moves_match_evaluator': True,
            'quality': {'actor_moves': len(actor_rows), 'cp_comparable': len(losses),
                        'cp_unavailable': dict(missing), 'finite_search_inversions': inversions,
                        'mean_raw_cp_difference': mean(losses) if losses else None,
                        'median_raw_cp_difference': median(losses) if losses else None,
                        'mean_nonnegative_cp_difference': mean(max(0, v) for v in losses) if losses else None,
                        'threshold_counts': {str(t): sum(v >= t for v in losses) for t in (100, 200, 300)},
                        'threshold_denominator': len(losses),
                        'scope': 'Executed actor moves only; exploratory fixed-node reference, not calibrated chess value'},
            'timing': {'decision_image_to_intent': distribution(decisions),
                       'intent_to_conclusive_verification': distribution(resolutions),
                       'scope': 'Wall intervals include orchestration and recording; not pure inference time or compute'},
            'limitations': ['No causal error label from a failed click or move alone',
                            'No Elo or grandmaster inference',
                            'Per-run versions and interventions require separate audit; no pooling here',
                            'Partial games are selected prefixes; move quality excludes unresolved and rejected intents',
                            'Hash and sequence consistency do not prove visual meaning or tool isolation']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('evaluation', type=Path)
    parser.add_argument('--actor', required=True, choices=['white', 'black'])
    parser.add_argument('--pgn', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = [p.read_bytes() for p in (args.run, args.evaluation, args.pgn)]
    run, evaluation = (json.loads(value) for value in raw[:2])
    if hashlib.sha256(raw[2]).hexdigest() != evaluation['pgn_sha256']:
        raise ValueError('PGN differs from evaluated source')
    result = game_metrics(run, evaluation, actor=args.actor)
    result['sources'] = [{'path': str(path.resolve()), 'sha256': hashlib.sha256(value).hexdigest()}
                         for path, value in zip((args.run, args.evaluation, args.pgn), raw)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(args.output.resolve())


if __name__ == '__main__':
    main()

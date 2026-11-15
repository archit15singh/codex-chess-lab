"""Private post-response scoring; the operator must first verify actor completion."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import chess
import chess.pgn

from . import evaluate as evaluator
from . import position_trial
from .corpus import common_rules
from .engine_budget import engine_allowance

NODES = 100_000


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('nonfinite JSON constant')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=constant)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be a timezone-aware string')
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('timestamp must be timezone-aware')
    return parsed


def confined(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError('expected relative corpus path')
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError('corpus path escapes its root')
    return path


def hashes(paths):
    return {str(path): digest(path.read_bytes()) if path.exists() else None for path in paths}


def unchanged(expected):
    for name, value in expected.items():
        path = Path(name)
        observed = digest(path.read_bytes()) if path.exists() else None
        if observed != value:
            raise ValueError('scoring input/source changed: ' + name)


def legal(board, move):
    try:
        return chess.Move.from_uci(move) in board.legal_moves
    except ValueError:
        return False


def stage_score(path, stage, manifest, launched, board):
    """Validate saved raw/parsed evidence before using any actor answer."""
    missing = {'present': False, 'status': 'missing', 'legal': None,
               'on_time_legal': False, 'latency_seconds': None}
    if not path.exists():
        return missing
    try:
        record = strict_json(path.read_bytes())
        fields = {'received_at', 'late', 'validation_error', 'response', 'raw_utf8',
                  'raw_base64', 'response_sha256', 'feedback'}
        if not isinstance(record, dict) or set(record) != fields:
            raise ValueError('invalid submission record schema')
        received = timestamp(record['received_at'])
        latency = (received - timestamp(launched['dispatch_requested_at'])).total_seconds()
        late = received >= timestamp(launched['deadline'])
        if latency < 0 or type(record['late']) is not bool or record['late'] != late:
            raise ValueError('inconsistent submission timing')
        raw = base64.b64decode(record['raw_base64'], validate=True)
        if digest(raw) != record['response_sha256'] or raw.decode('utf-8', errors='replace') != record['raw_utf8']:
            raise ValueError('raw submission bytes/hash mismatch')
        value = None
        try:
            value = strict_json(raw)
            position_trial.validate_response(value)
            valid = True
        except (ValueError, TypeError):
            valid = False
        if valid:
            if record['validation_error'] is not None or record['response'] != value:
                raise ValueError('saved response differs from validated raw response')
        elif (record['response'] is not None or not isinstance(record['validation_error'], str)
              or not record['validation_error']):
            raise ValueError('malformed response record is inconsistent')
        is_legal = legal(board, value['move']) if valid else None
        feedback = (('legal' if is_legal else 'illegal')
                    if valid and stage == 'initial' and manifest['arm'] in position_trial.LEGALITY and not late
                    else None)
        if record['feedback'] != feedback:
            raise ValueError('submission feedback differs from assigned intervention')
        result = {'present': True, 'status': 'legal' if is_legal else 'illegal' if valid else 'malformed_response',
                  'received_at': record['received_at'], 'latency_seconds': latency, 'late': late,
                  'format_valid': valid, 'legal': is_legal, 'on_time_legal': bool(is_legal and not late),
                  'response_sha256': digest(raw)}
        if valid:
            rules = common_rules(board)
            correct = sum(value['castling'][side][wing] == rules['castling'][side][wing]
                          for side in ('white', 'black') for wing in ('kingside', 'queenside'))
            side_correct = value['side_to_move'] == rules['side_to_move']
            ep_correct = value['en_passant_square'] == rules['en_passant_square']
            result.update({'move': value['move'], 'confidence': value['confidence'],
                           'transcription': position_trial.transcription_score(value,
                               {chess.square_name(s): p.symbol() for s, p in board.piece_map().items()}),
                           'requested_rules': {'side_to_move_correct': side_correct,
                               'castling_correct_flags': correct, 'castling_total_flags': 4,
                               'unknown_castling_flags': sum(flag == 'unknown'
                                   for flags in value['castling'].values() for flag in flags.values()),
                               'en_passant_correct': ep_correct,
                               'en_passant_unknown': value['en_passant_square'] == 'unknown',
                               'exact_requested_rules': side_correct and ep_correct and correct == 4,
                               'halfmove_clock': 'not requested in response schema'}})
        return result
    except (ValueError, TypeError, KeyError) as exc:
        return {**missing, 'present': True, 'status': 'invalid_record',
                'record_error': str(exc)}


def one_ply_pgn(board, move):
    game = chess.pgn.Game()
    game.setup(board)
    game.headers['SetUp'] = '1'
    game.headers['FEN'] = board.fen()
    game.add_variation(chess.Move.from_uci(move))
    after = board.copy(stack=False)
    after.push_uci(move)
    outcome = after.outcome(claim_draw=False)
    game.headers['Result'] = outcome.result() if outcome else '*'
    return str(game) + '\n'


def quality_summary(evaluation, board, move, secondary):
    analysis = evaluation['engine_analysis']
    rows = analysis['rows']
    if (evaluation['plies'] != 1 or len(rows) != 1 or rows[0]['fen'] != board.fen()
            or rows[0]['move'] != move or rows[0]['turn'] != ('white' if board.turn else 'black')
            or analysis['nodes_per_search'] != NODES or analysis['searches_per_ply'] != 2
            or analysis['options'].get('Threads') != 1 or analysis['options'].get('Hash') != 16
            or analysis['hash_reset_each_search'] is not True):
        raise ValueError('reference evaluator root/policy differs from frozen protocol')
    row = rows[0]
    scores = [row['best'], row['selected']]
    reasons = []
    if any(score['mate'] is not None for score in scores):
        reasons.append('mate_score')
    if any(score['lowerbound'] or score['upperbound'] for score in scores):
        reasons.append('bounded_score')
    if not reasons and any(score['cp'] is None for score in scores):
        reasons.append('missing_score')
    delta = None
    if not reasons:
        if any(type(s['cp']) not in (int, float) or not math.isfinite(s['cp']) for s in scores):
            raise ValueError('reference centipawns must be finite')
        delta = scores[0]['cp'] - scores[1]['cp']
        if not math.isfinite(delta) or row['cp_loss_raw'] != delta:
            raise ValueError('reference difference is inconsistent')
    elif row['cp_loss_raw'] is not None:
        raise ValueError('reference invented centipawn difference for nonexact scores')
    return {'status': 'analyzed', 'cp_comparable': delta is not None,
            'cp_unavailable_reasons': reasons, 'cp_loss_raw': delta,
            'cp_loss_nonnegative': max(0, delta) if delta is not None else None,
            'finite_search_inversion': delta < 0 if delta is not None else None,
            'thresholds': {str(t): delta >= t if delta is not None else None for t in (100, 200, 300)},
            'best_move_agreement': bool(scores[0]['pv'] and scores[0]['pv'][0] == move),
            'late_quality_secondary_only': secondary,
            'warning': 'Snapshot-root bounded-search comparison, not a whole-game value or strength rating.'}


def score_trial(trial: Path, output: Path, *, actor_completed: bool,
                completion_evidence: Path, engine: Path | None = None):
    """Operator-gated scoring; this function cannot attest host completion itself."""
    if actor_completed is not True:
        raise ValueError('operator must verify authoritative actor-handle completion first')
    completion_evidence = completion_evidence.resolve(strict=True)
    if not completion_evidence.is_file():
        raise ValueError('completion evidence must be a controller evidence file')
    output.mkdir(parents=False, exist_ok=False)
    write = position_trial.write_new
    expected = {}
    try:
        sources = [Path(__file__), Path(evaluator.__file__), Path(position_trial.__file__),
                   Path(__file__).with_name('engine_budget.py'), Path(__file__).with_name('corpus.py')]
        trial = trial.resolve(strict=True)
        expected = hashes(sources + [completion_evidence] +
                          [trial / n for n in ('manifest.json', 'launch.json', 'initial.json', 'final.json', 'attachment.json')])
        write(output / 'inputs.json', {'schema_version': 1, 'trial': str(trial), 'hashes': expected,
              'actor_completion_gate': {'operator_attested_completed': True,
                                       'evidence_path': str(completion_evidence),
                                       'warning': 'Operator gate; not a host-status verifier or sandbox.'}})
        manifest = strict_json((trial / 'manifest.json').read_bytes())
        launched = strict_json((trial / 'launch.json').read_bytes())
        if (manifest.get('schema_version') != 1 or manifest.get('arm') not in position_trial.ARMS
                or not isinstance(manifest.get('item_id'), str)):
            raise ValueError('invalid trial manifest schema')
        if launched['manifest_sha256'] != expected[str(trial / 'manifest.json')]:
            raise ValueError('trial manifest differs from launch commitment')
        dispatch, deadline = timestamp(launched['dispatch_requested_at']), timestamp(launched['deadline'])
        prepared, started = timestamp(manifest['prepared_at']), timestamp(manifest['preparation_started'])
        if not started <= prepared <= dispatch or (deadline - dispatch).total_seconds() != manifest['actor_seconds']:
            raise ValueError('invalid launch/preparation timeline')
        if manifest['actor_seconds'] != position_trial.ACTOR_SECONDS:
            raise ValueError('actor deadline differs from frozen mechanics')
        position_trial.verify_inputs(trial, manifest)
        corpus = Path(manifest['corpus']).resolve(strict=True)
        corpus_manifest = strict_json((corpus / 'manifest.json').read_bytes())
        if corpus_manifest.get('status') != 'sealed':
            raise ValueError('scoring requires a sealed corpus')
        item = position_trial.item_state(corpus, manifest['item_id'])
        player_path = confined(corpus, item['player_path'])
        player = strict_json(player_path.read_bytes())
        image = confined(corpus, player['image']['path'])
        if player_path != Path(manifest['player_path']).resolve() or image != Path(manifest['image_path']).resolve():
            raise ValueError('trial paths differ from corpus item')
        for path in (corpus / 'evaluator/items.json', player_path, image):
            if corpus_manifest['files'].get(str(path.relative_to(corpus))) != digest(path.read_bytes()):
                raise ValueError('corpus file differs from sealed manifest')
        expected.update(hashes([corpus / 'manifest.json', corpus / 'evaluator/items.json', player_path, image]))
        write(output / 'corpus-inputs.json', {'hashes': {str(path): expected[str(path)] for path in
              (corpus / 'manifest.json', corpus / 'evaluator/items.json', player_path, image)}})
        board = chess.Board(item['fen'])
        if not board.is_valid() or board.is_game_over(claim_draw=False):
            raise ValueError('invalid or terminal snapshot root')
        replay = chess.Board()
        for uci in item['history_uci']:
            replay.push_uci(uci)
        if replay.fen() != board.fen() or len(item['history_uci']) != item['ply']:
            raise ValueError('source history differs from snapshot')
        occupancy = {chess.square_name(s): piece.symbol() for s, piece in board.piece_map().items()}
        if item['occupancy'] != occupancy or player['rules'] != common_rules(board) or player['item_id'] != item['item_id']:
            raise ValueError('oracle occupancy/common metadata differs from snapshot')
        initial = stage_score(trial / 'initial.json', 'initial', manifest, launched, board)
        final = stage_score(trial / 'final.json', 'final', manifest, launched, board)
        integrity_valid = all(stage['status'] != 'invalid_record' for stage in (initial, final))
        if final['present'] and not initial['present']:
            raise ValueError('final submission exists without initial record')
        revision_seconds = None
        if initial.get('received_at') and final.get('received_at'):
            revision_seconds = (timestamp(final['received_at']) - timestamp(initial['received_at'])).total_seconds()
            if revision_seconds < 0:
                raise ValueError('final submission predates initial')
        measurements = {'schema_version': 1, 'attempted_trials': 1,
                        'item_id': item['item_id'], 'family_id': item['family_id'], 'split': item['split'],
                        'source_ply': item['ply'], 'arm': manifest['arm'],
                        'desired_model': manifest['desired_model'], 'desired_reasoning': manifest['desired_reasoning'],
                        'settings_warning': 'Desired settings require independent actual host readback.',
                        'initial': initial, 'final': final, 'submission_records_valid': integrity_valid,
                        'deadline_success': integrity_valid and final['on_time_legal'],
                        'timing': {'preparation_seconds': (prepared-started).total_seconds(),
                                   'prepared_to_dispatch_seconds': (dispatch-prepared).total_seconds(),
                                   'revision_seconds': revision_seconds},
                        'root_semantics': 'FEN snapshot, including counters/rights; no prior repetition history supplied to engine.',
                        'repetition_claims_assessed': False, 'whole_game_value_assessed': False,
                        'history_provenance_sha256': digest(json.dumps(item['history_uci']).encode()),
                        'chess_version': chess.__version__, 'python_version': sys.version}
        write(output / 'measurements.json', measurements)
        unchanged(expected)
        if final['legal'] and integrity_valid:
            if engine is None:
                raise ValueError('legal final choice requires a configured reference engine')
            engine = engine.resolve(strict=True)
            engine_sha = digest(engine.read_bytes())
            expected[str(engine)] = engine_sha
            if engine_sha != corpus_manifest['engine']['binary_sha256']:
                raise ValueError('reference binary differs from corpus pinned engine')
            with (output / 'reference.pgn').open('x') as stream:
                stream.write(one_ply_pgn(board, final['move']))
            operation = 'position-score:' + digest(str(output.resolve()).encode())
            with engine_allowance(corpus, operation, reserve_seconds=13) as allowance:
                evaluation = evaluator.evaluate(output / 'reference.pgn', engine=engine,
                    nodes=NODES, hash_mb=16, timeout=3, total_timeout=10)
            if evaluation['engine_analysis']['binary_sha256'] != engine_sha:
                raise ValueError('reference engine identity changed')
            quality = quality_summary(evaluation, board, final['move'], final['late'])
            write(output / 'evaluation.json', evaluation)
            quality['budget'] = {'path': str(allowance.budget_path),
                                 'reservation_id': allowance.reservation_id, 'reserved_seconds': allowance.allowed_seconds}
        else:
            quality = {'status': 'not_eligible',
                       'reason': final['status'] if integrity_valid else 'invalid_submission_record',
                       'cp_comparable': False}
        unchanged(expected)
        result = {**measurements, 'quality': quality,
                  'completed_at': datetime.now(timezone.utc).isoformat()}
        write(output / 'score.json', result)
        return result
    except BaseException as exc:
        write(output / 'failure.json', {'schema_version': 1, 'attempted_trials': 1,
              'error_type': type(exc).__name__, 'message': str(exc),
              'note': 'Preserve this scoring attempt; no overwrite or automatic retry. Include in coverage denominator.',
              'input_hashes': expected})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trial', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--actor-completed', action='store_true')
    parser.add_argument('--completion-evidence', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = score_trial(args.trial, args.output, engine=args.engine,
            actor_completed=args.actor_completed, completion_evidence=args.completion_evidence)
    except (ValueError, OSError, KeyError, TypeError, chess.engine.EngineError) as exc:
        parser.exit(2, f'position scoring failed ({type(exc).__name__}); inspect private failure/input records.\n')
    print(json.dumps({'score_path': str(args.output / 'score.json'),
                      'sha256': digest((args.output / 'score.json').read_bytes()),
                      'quality_status': result['quality']['status']}, sort_keys=True))


if __name__ == '__main__':
    main()

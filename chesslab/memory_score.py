"""Offline sequence fidelity scoring after authoritative actor completion; no engine."""
import argparse
import json
from pathlib import Path

import chess

from . import memory_trial as trial
from . import position_trial as static
from .corpus import common_rules


def hashes(paths):
    return {str(p): static.sha(p) if p.exists() else None for p in paths}


def unchanged(expected):
    if hashes([Path(p) for p in expected]) != expected:
        raise ValueError('scoring input or source changed')


def source_boards(manifest):
    """Require a unique final source game matching every selected frame and legal ply."""
    corpus = Path(manifest['corpus'])
    seal = trial.strict_json((corpus / 'manifest.json').read_bytes())
    path = corpus / 'evaluator/families.json'
    if seal['files'].get('evaluator/families.json') != static.sha(path):
        raise ValueError('source histories differ from sealed corpus')
    sequence = manifest['sequence']
    candidates = [f for f in trial.strict_json(path.read_bytes())['families']
                  if f['split'] == 'final' and len(f['frames']) >= len(sequence['frames'])
                  and all(f['frames'][i]['ply'] == frame['ply'] and f['frames'][i]['image'] == frame['image']
                          for i, frame in enumerate(sequence['frames']))]
    if len(candidates) != 1:
        raise ValueError('expected unique final source history for sequence')
    family = candidates[0]
    board, boards = chess.Board(), []
    for ply, frame in enumerate(family['frames'][:len(sequence['frames'])]):
        if ply:
            board.push_uci(family['moves_uci'][ply - 1])
        if not board.is_valid() or frame['fen'] != board.fen() or frame['rules'] != common_rules(board):
            raise ValueError('source history/frame state mismatch')
        boards.append(board.copy(stack=False))
    if sequence['initial_rules'] != common_rules(boards[0]):
        raise ValueError('initial metadata differs from source history')
    return family, boards, path


def fidelity(value, board, previous, last_move):
    occupancy = {chess.square_name(s): p.symbol() for s, p in board.piece_map().items()}
    adapted = {k: v for k, v in value.items() if k not in {'last_move_uci', 'recall'}}
    adapted['move'] = 'a1a2'
    rules = common_rules(board)
    flags = [(value['castling'][c][w], rules['castling'][c][w])
             for c in ('white', 'black') for w in ('kingside', 'queenside')]
    recall_truth = {s: previous.piece_at(chess.parse_square(s)).symbol()
                    if previous.piece_at(chess.parse_square(s)) else '.' for s in ('d4', 'e5')}
    return {'transcription': static.transcription_score(adapted, occupancy),
            'last_move_correct': value['last_move_uci'] == last_move,
            'last_move_unknown': value['last_move_uci'] is None,
            'recall_correct_squares': sum(value['recall'][s] == p for s, p in recall_truth.items()),
            'recall_total_squares': 2, 'recall_unknown_squares': sum(p == '?' for p in value['recall'].values()),
            'side_to_move_correct': value['side_to_move'] == rules['side_to_move'],
            'side_to_move_unknown': value['side_to_move'] == 'unknown',
            'castling_correct_flags': sum(a == b for a, b in flags), 'castling_total_flags': 4,
            'castling_unknown_flags': sum(a == 'unknown' for a, _ in flags),
            'en_passant_correct': value['en_passant_square'] == rules['en_passant_square'],
            'en_passant_unknown': value['en_passant_square'] == 'unknown', 'confidence': value['confidence']}


def score_sequence(directory, output, *, actor_completed, completion_evidence):
    if actor_completed is not True:
        raise ValueError('operator must verify authoritative actor-handle completion first')
    directory, completion_evidence = directory.resolve(strict=True), completion_evidence.resolve(strict=True)
    if not completion_evidence.is_file() or completion_evidence.is_relative_to(directory):
        raise ValueError('completion evidence must be a separate controller file')
    output = output.resolve()
    if output.is_relative_to(directory) or directory.is_relative_to(output):
        raise ValueError('score output and trial must occupy disjoint directory trees')
    write, expected = static.write_new, {}
    output.mkdir(parents=False, exist_ok=False)
    try:
        expected = hashes([Path(__file__).resolve(), Path(trial.__file__).resolve(),
                           Path(static.__file__).resolve(), Path(__file__).with_name('corpus.py'), completion_evidence]
                          + list(directory.rglob('*.json')))
        write(output / 'inputs.json', {'hashes': expected, 'trial': str(directory),
                         'actor_completion_gate': {'operator_attested_completed': True,
                                                   'evidence_path': str(completion_evidence),
                                                   'warning': 'Operator gate, not host-status verification or a sandbox.'}})
        manifest = trial.verify_inputs(directory)
        family, boards, source_path = source_boards(manifest)
        expected.update(hashes([Path(p) for p in manifest['inputs']] + [source_path]))
        write(output / 'corpus-inputs.json', {'hashes': expected})
        rows, prior, halted, last_received = [], [], False, None
        for stage, ply in enumerate(manifest['sequence']['checkpoints'], 1):
            folder = trial.stage_path(directory, stage)
            row = {'stage': stage, 'checkpoint_ply': ply, 'status': 'not_opened',
                   'present': False, 'on_time_exact_board': False}
            if folder.exists():
                if halted:
                    raise ValueError('stage opened after failed or missing prior checkpoint')
                opened = trial.strict_json((folder / 'open.json').read_bytes())
                beginning, deadline = trial.timestamp(opened['opened_at']), trial.timestamp(opened['deadline'])
                if ((deadline - beginning).total_seconds() != trial.ACTOR_SECONDS
                        or beginning < trial.timestamp(manifest['prepared_at'])
                        or (last_received is not None and beginning < last_received)):
                    raise ValueError('invalid stage chronology/deadline')
                delivered = {k: v for k, v in opened.items() if k not in {'opened_at', 'deadline'}}
                if delivered != trial.expected_delivery(manifest, stage, prior):
                    raise ValueError('stage delivery differs from assigned information channel')
                row.update({'status': 'missing', 'opened_at': opened['opened_at'], 'deadline': opened['deadline']})
                if (folder / 'response.json').exists():
                    record = trial.read_record(folder)
                    prior.append(record)
                    last_received = trial.timestamp(record['received_at'])
                    valid = record['validation_error'] is None
                    row.update({'present': True, 'status': 'late' if record['late'] else 'valid' if valid else 'malformed',
                                'format_valid': valid, 'late': record['late'],
                                'latency_seconds': (last_received - beginning).total_seconds(),
                                'response_sha256': record['response_sha256']})
                    if valid:
                        previous = manifest['sequence']['checkpoints'][stage - 2] if stage > 1 else 0
                        row.update(fidelity(record['response'], boards[ply], boards[previous], family['moves_uci'][ply - 1]))
                        row['on_time_exact_board'] = not record['late'] and row['transcription']['exact_board']
                    halted = record['late'] or not valid
                else:
                    halted = True
            else:
                halted = True
            rows.append(row)
        unchanged(expected)
        # Detect additions/removals during scoring, including missing response arrival.
        if set(directory.rglob('*.json')) != {Path(p) for p in expected if Path(p).is_relative_to(directory)}:
            raise ValueError('trial files changed during scoring')
        result = {'schema_version': 1, 'condition': manifest['condition'],
                  'sequence_id': manifest['sequence']['sequence_id'], 'family_id': family['family_id'],
                  'checkpoint_denominator': 4, 'present_responses': sum(r['present'] for r in rows),
                  'on_time_exact_boards': sum(r['on_time_exact_board'] for r in rows),
                  'primary_final_exact_board': rows[-1]['on_time_exact_board'], 'checkpoints': rows,
                  'warning': 'Overlapping sequences share family/game clusters. Fidelity experiment; no chess strength claim.'}
        write(output / 'result.json', result)
        return result
    except BaseException as exc:
        write(output / 'failure.json', {'error_type': type(exc).__name__, 'error': str(exc),
            'checkpoint_denominator': 4, 'integrity_valid': False,
            'primary_final_exact_board': False, 'note': 'Preserve as an integrity failure; do not replace sequence.'})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--actor-completed', action='store_true')
    parser.add_argument('--completion-evidence', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(score_sequence(args.directory, args.output, actor_completed=args.actor_completed,
                                   completion_evidence=args.completion_evidence), indent=2))


if __name__ == '__main__':
    main()

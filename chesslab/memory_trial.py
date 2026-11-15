"""Mechanical, file-based sequence delivery. No chess rules or evaluator access."""
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re

from . import position_trial as static

CONDITIONS = {'internal', 'record'}
ACTOR_SECONDS = 60
PIECES = set('PNBRQKpnbrqk.?')


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


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def confined(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError('expected relative corpus path')
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError('corpus path escapes root')
    return path


def validate_response(value):
    keys = {'last_move_uci', 'piece_map', 'side_to_move', 'confidence', 'castling',
            'en_passant_square', 'recall'}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError('invalid memory response keys')
    last = value['last_move_uci']
    if last is not None and (not isinstance(last, str) or not re.fullmatch('[a-h][1-8][a-h][1-8][qrbn]?', last)):
        raise ValueError('last_move_uci must be UCI or null for unknown')
    adapted = {key: item for key, item in value.items() if key not in {'last_move_uci', 'recall'}}
    adapted['move'] = 'a1a2'  # Format validation only; never asks a chess legality function.
    static.validate_response(adapted)
    recall = value['recall']
    if (not isinstance(recall, dict) or set(recall) != {'d4', 'e5'}
            or any(not isinstance(p, str) or p not in PIECES for p in recall.values())):
        raise ValueError('recall requires d4/e5 piece symbols, dot or question mark')


@contextmanager
def exclusive(directory):
    """A crash leaves the lock for controller recovery after execution has stopped."""
    path = directory / '.mutation.lock'
    with path.open('x') as stream:
        stream.write('Exclusive mechanics operation; no automatic stale-lock recovery.\n')
    try:
        yield
    finally:
        path.unlink()


def prepare(corpus, sequence_id, condition, output):
    if condition not in CONDITIONS:
        raise ValueError('unknown condition')
    corpus = corpus.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    static.write_new(output / 'preparation.json', {'started_at': static.now().isoformat()})
    try:
        seal_path, sequences_path = corpus / 'manifest.json', corpus / 'player/sequences.json'
        seal = strict_json(seal_path.read_bytes())
        if seal.get('status') != 'sealed' or seal['files'].get('player/sequences.json') != static.sha(sequences_path):
            raise ValueError('unsealed or changed sequence source')
        choices = strict_json(sequences_path.read_bytes())['sequences']
        selected = [s for s in choices if s['sequence_id'] == sequence_id]
        if len(selected) != 1:
            raise ValueError('expected one sequence')
        sequence = selected[0]
        if set(sequence) != {'sequence_id', 'orientation', 'initial_rules', 'checkpoints', 'frames'}:
            raise ValueError('unexpected player sequence fields')
        checkpoints, frames = sequence['checkpoints'], sequence['frames']
        if (checkpoints not in ([6, 12, 18, 24], [10, 20, 30, 40])
                or len(frames) != checkpoints[-1] + 1 or sequence['orientation'] != 'white'):
            raise ValueError('sequence differs from frozen checkpoint policy')
        inputs = {str(seal_path): static.sha(seal_path), str(sequences_path): static.sha(sequences_path),
                  str(Path(__file__).resolve()): static.sha(Path(__file__)),
                  str(Path(static.__file__).resolve()): static.sha(Path(static.__file__))}
        for ply, frame in enumerate(frames):
            if set(frame) != {'ply', 'image'} or type(frame['ply']) is not int or frame['ply'] != ply:
                raise ValueError('noncontiguous frame identity')
            if set(frame['image']) != {'path', 'sha256'}:
                raise ValueError('unexpected image fields')
            relative = frame['image']['path']
            if not isinstance(relative, str) or not relative.startswith('images/') or not relative.endswith('.png'):
                raise ValueError('expected corpus PNG image path')
            path = confined(corpus, relative)
            observed = static.sha(path)
            if observed != frame['image']['sha256'] or seal['files'].get(frame['image']['path']) != observed:
                raise ValueError('frame image differs from sealed corpus')
            inputs[str(path)] = observed
        # Validate common initial metadata using the static format validator only.
        rules = sequence['initial_rules']
        if (not isinstance(rules, dict)
                or set(rules) != {'side_to_move', 'castling', 'en_passant_square', 'halfmove_clock'}
                or type(rules['halfmove_clock']) is not int or rules['halfmove_clock'] < 0):
            raise ValueError('unexpected initial metadata fields')
        sample = {'move': 'a1a2', 'piece_map': {s: '.' for s in static.SQUARES}, 'confidence': 0,
                  **{k: rules[k] for k in ('side_to_move', 'castling', 'en_passant_square')}}
        static.validate_response(sample)
        manifest = {'schema_version': 1, 'corpus': str(corpus), 'condition': condition,
                    'sequence': sequence, 'inputs': inputs, 'actor_seconds': ACTOR_SECONDS,
                    'prepared_at': static.now().isoformat()}
        static.write_new(output / 'manifest.json', manifest)
        static.write_new(output / 'prepared.json', {'manifest_sha256': static.sha(output / 'manifest.json')})
    except BaseException as exc:
        static.write_new(output / 'preparation-failure.json', {'error_type': type(exc).__name__})
        raise
    return {'prepared': True, 'condition': condition, 'checkpoints': 4,
            'manifest_sha256': static.sha(output / 'manifest.json')}


def verify_inputs(directory):
    if static.sha(directory / 'manifest.json') != strict_json((directory / 'prepared.json').read_bytes())['manifest_sha256']:
        raise ValueError('prepared manifest changed')
    manifest = strict_json((directory / 'manifest.json').read_bytes())
    if manifest['actor_seconds'] != ACTOR_SECONDS or manifest['condition'] not in CONDITIONS:
        raise ValueError('invalid mechanics policy')
    for name, expected in manifest['inputs'].items():
        if static.sha(Path(name)) != expected:
            raise ValueError('prepared input or source changed')
    return manifest


def stage_path(directory, number):
    return directory / f'stage-{number:02d}'


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    return parsed


def read_record(folder):
    """Validate exact preserved bytes before allowing advancement or record delivery."""
    record = strict_json((folder / 'response.json').read_bytes())
    if set(record) != {'received_at', 'late', 'validation_error', 'response', 'raw_utf8',
                       'raw_base64', 'response_sha256', 'open_sha256'}:
        raise ValueError('invalid response record keys')
    opened = strict_json((folder / 'open.json').read_bytes())
    raw = base64.b64decode(record['raw_base64'], validate=True)
    if (base64.b64encode(raw).decode('ascii') != record['raw_base64']
            or digest(raw) != record['response_sha256']
            or raw.decode('utf-8', errors='replace') != record['raw_utf8']
            or static.sha(folder / 'open.json') != record['open_sha256']):
        raise ValueError('raw response or open commitment mismatch')
    received = timestamp(record['received_at'])
    if (received < timestamp(opened['opened_at']) or type(record['late']) is not bool
            or record['late'] != (received >= timestamp(opened['deadline']))):
        raise ValueError('inconsistent response timing')
    try:
        value = strict_json(raw)
        validate_response(value)
    except (ValueError, TypeError):
        if record['response'] is not None or not isinstance(record['validation_error'], str) or not record['validation_error']:
            raise ValueError('malformed response record inconsistent')
    else:
        if record['response'] != value or record['validation_error'] is not None:
            raise ValueError('response differs from raw bytes')
    return record


def stopped(directory, stage, reason):
    path = directory / 'stopped.json'
    if not path.exists():
        static.write_new(path, {'stage': stage, 'reason': reason, 'recorded_at': static.now().isoformat()})
    return {'status': 'stopped', **strict_json(path.read_bytes())}


def expected_delivery(manifest, stage, prior):
    seq = manifest['sequence']
    previous = seq['checkpoints'][stage - 2] if stage > 1 else 0
    checkpoint = seq['checkpoints'][stage - 1]
    first = previous + 1 if stage > 1 else 0
    value = {'status': 'open', 'stage': stage, 'checkpoint_ply': checkpoint,
             'recall_checkpoint_ply': previous, 'orientation': seq['orientation'],
             'frames': [{'ply': f['ply'], 'path': str(confined(Path(manifest['corpus']), f['image']['path'])),
                         'sha256': f['image']['sha256']} for f in seq['frames'][first:checkpoint + 1]]}
    if stage == 1:
        value['initial_rules'] = seq['initial_rules']
    if manifest['condition'] == 'record':
        value['own_prior_responses'] = [{'stage': n, 'raw_base64': r['raw_base64'], 'raw_utf8': r['raw_utf8']}
                                        for n, r in enumerate(prior, 1)]
    return value


def verify_delivery(directory, manifest, stage, prior):
    delivery = strict_json((stage_path(directory, stage) / 'open.json').read_bytes())
    beginning, deadline = timestamp(delivery['opened_at']), timestamp(delivery['deadline'])
    if ((deadline - beginning).total_seconds() != ACTOR_SECONDS
            or beginning < timestamp(manifest['prepared_at'])
            or (prior and beginning < timestamp(prior[-1]['received_at']))):
        raise ValueError('invalid stage chronology/deadline')
    if {k: v for k, v in delivery.items() if k not in {'opened_at', 'deadline'}} != expected_delivery(manifest, stage, prior):
        raise ValueError('stage delivery differs from assigned information channel')
    return delivery


def open_next(directory):
    with exclusive(directory):
        manifest = verify_inputs(directory)
        if (directory / 'stopped.json').exists():
            return {'status': 'stopped', **strict_json((directory / 'stopped.json').read_bytes())}
        sequence = manifest['sequence']
        prior = []
        for index, checkpoint in enumerate(sequence['checkpoints'], 1):
            folder = stage_path(directory, index)
            response = folder / 'response.json'
            if response.exists():
                verify_delivery(directory, manifest, index, prior)
                saved = read_record(folder)
                prior.append(saved)
                if saved['late'] or saved['validation_error'] is not None:
                    return stopped(directory, index, 'late' if saved['late'] else 'malformed')
                continue
            if folder.exists():
                delivery = verify_delivery(directory, manifest, index, prior)
                if static.now() >= datetime.fromisoformat(delivery['deadline']):
                    return stopped(directory, index, 'missing_at_deadline')
                return delivery
            folder.mkdir()
            opened = static.now()
            delivery = {**expected_delivery(manifest, index, prior), 'opened_at': opened.isoformat(),
                        'deadline': (opened + timedelta(seconds=ACTOR_SECONDS)).isoformat()}
            static.write_new(folder / 'open.json', delivery)
            return delivery
        return {'status': 'completed', 'checkpoints': 4}


def submit(directory, stage, response_path):
    with exclusive(directory):
        manifest = verify_inputs(directory)
        if type(stage) is not int or stage not in range(1, 5):
            raise ValueError('unknown stage')
        if (directory / 'stopped.json').exists():
            raise ValueError('sequence already stopped')
        folder = stage_path(directory, stage)
        if any(not (stage_path(directory, n) / 'response.json').exists() for n in range(1, stage)):
            raise ValueError('prior checkpoint response required')
        prior = []
        for n in range(1, stage):
            verify_delivery(directory, manifest, n, prior)
            saved = read_record(stage_path(directory, n))
            if saved['late'] or saved['validation_error'] is not None:
                raise ValueError('prior checkpoint failed')
            prior.append(saved)
        delivery = verify_delivery(directory, manifest, stage, prior)
        raw, received = response_path.read_bytes(), static.now()
        late = received >= datetime.fromisoformat(delivery['deadline'])
        value, error = None, None
        try:
            value = strict_json(raw)
            validate_response(value)
        except (ValueError, TypeError) as exc:
            value, error = None, str(exc)
        static.write_new(folder / 'response.json', {
            'received_at': received.isoformat(), 'late': late, 'validation_error': error,
            'response': value, 'raw_utf8': raw.decode('utf-8', errors='replace'),
            'raw_base64': base64.b64encode(raw).decode('ascii'), 'response_sha256': digest(raw),
            'open_sha256': static.sha(folder / 'open.json')})
        if late or error is not None:
            stopped(directory, stage, 'late' if late else 'malformed')
        return {'recorded': stage, 'late': late, 'format_valid': error is None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('corpus', type=Path)
    p.add_argument('sequence_id')
    p.add_argument('condition', choices=sorted(CONDITIONS))
    p.add_argument('output', type=Path)
    p = sub.add_parser('open')
    p.add_argument('directory', type=Path)
    p = sub.add_parser('submit')
    p.add_argument('directory', type=Path)
    p.add_argument('stage', type=int)
    p.add_argument('response', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.corpus, args.sequence_id, args.condition, args.output)
    elif args.command == 'open':
        result = open_next(args.directory)
    else:
        result = submit(args.directory, args.stage, args.response)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

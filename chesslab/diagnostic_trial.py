"""Standalone mechanical diagnostic delivery/submission. No chess rules or hints.

The player submits before parent notification, so delayed controller delivery
does not silently change the response timestamp. Actual host traces remain an
independent audit requirement; these files do not enforce a tool sandbox.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys


TASKS = {'perception', 'history', 'correction', 'move'}
CONDITIONS = {'unaided', 'state', 'history', 'feedback', 'no_feedback',
              'reasoning_medium', 'reasoning_high', 'search', 'candidate', 'sham'}
SQUARES = {f'{f}{r}' for f in 'abcdefgh' for r in '12345678'}
PIECES = set('PNBRQKpnbrqk.?')


def now():
    return datetime.now(timezone.utc)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError('duplicate JSON key')
            result[k] = v
        return result
    def invalid(_):
        raise ValueError('nonfinite JSON value')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def write_new(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def move_format(value):
    return isinstance(value, str) and bool(re.fullmatch('[a-h][1-8][a-h][1-8][qrbn]?', value))


def piece_map(value, squares):
    return (isinstance(value, dict) and set(value) == set(squares)
            and all(isinstance(p, str) and p in PIECES for p in value.values()))


def validate_config(value):
    keys = {'trial_id', 'purpose', 'task', 'condition', 'model', 'effort', 'seconds', 'context'}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError('explicit diagnostic configuration required')
    if value['task'] not in TASKS or value['condition'] not in CONDITIONS:
        raise ValueError('unknown task or condition')
    if value['purpose'] not in {'pilot', 'training', 'development', 'heldout', 'synthetic'}:
        raise ValueError('unknown purpose')
    for key in ['trial_id', 'model', 'effort']:
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError('record trial identity and desired host settings')
    if type(value['seconds']) is not int or not 1 <= value['seconds'] <= 3600:
        raise ValueError('bounded integer response window required')
    context = value['context']
    common = {'orientation', 'rules'}
    if value['task'] == 'history':
        common.add('query')
    if value['task'] == 'correction':
        common.add('initial_proposal')
    extra = {'state': 'validated_state', 'history': 'history_record', 'feedback': 'feedback',
             'search': 'search', 'candidate': 'supplement', 'sham': 'supplement'}.get(value['condition'])
    if not isinstance(context, dict) or set(context) != common | ({extra} if extra else set()):
        raise ValueError('context contains missing or unassigned information')
    if context['orientation'] not in {'white', 'black'}:
        raise ValueError('orientation required')
    rules = context['rules']
    if (not isinstance(rules, dict) or set(rules) != {'side_to_move', 'castling', 'legal_en_passant_square'}
            or rules['side_to_move'] not in {'white', 'black'}
            or not isinstance(rules['castling'], str)
            or not re.fullmatch('[KQkq]+|-', rules['castling'])
            or rules['legal_en_passant_square'] is not None and rules['legal_en_passant_square'] not in SQUARES):
        raise ValueError('explicit common diagnostic rules metadata required')
    if value['task'] == 'history':
        query = context['query']
        if (not isinstance(query, dict) or set(query) != {'checkpoint_ply', 'squares'}
                or type(query['checkpoint_ply']) is not int or query['checkpoint_ply'] <= 0
                or not isinstance(query['squares'], list) or not query['squares']
                or len(set(query['squares'])) != len(query['squares'])
                or not set(query['squares']) <= SQUARES):
            raise ValueError('explicit past-state query required')
    if value['task'] == 'correction' and not move_format(context['initial_proposal']):
        raise ValueError('injected coordinate proposal required')
    if extra == 'validated_state' and not piece_map(context[extra], SQUARES):
        raise ValueError('complete declared state attachment required')
    if extra == 'feedback' and (value['task'] != 'correction' or context[extra] != 'The proposed move is illegal.'):
        raise ValueError('only the assigned fixed legality feedback is permitted')
    if extra == 'history_record':
        records = context[extra]
        if (value['task'] != 'history' or not isinstance(records, list) or not 1 <= len(records) <= 24
                or any(not isinstance(r, dict) or set(r) != {'ply', 'piece_map'}
                       or type(r['ply']) is not int or r['ply'] < 0
                       or not piece_map(r['piece_map'], SQUARES) for r in records)):
            raise ValueError('explicit history attachment required')
    if extra == 'search':
        search = context[extra]
        if (not isinstance(search, dict) or set(search) != {'move', 'nodes'}
                or not move_format(search['move']) or type(search['nodes']) is not int or search['nodes'] <= 0):
            raise ValueError('bounded search attachment required')
    if extra == 'supplement' and (not isinstance(context[extra], str) or not 1 <= len(context[extra]) <= 8000):
        raise ValueError('bounded candidate/sham attachment required')


def prepare(directory, config, images, *, image_plies=None):
    validate_config(config)
    if not isinstance(images, list) or not 1 <= len(images) <= 24:
        raise ValueError('explicit bounded image allowlist required')
    if config['task'] == 'history':
        if (not isinstance(image_plies, list) or len(image_plies) != len(images)
                or any(type(n) is not int or n < 0 for n in image_plies)
                or image_plies != sorted(set(image_plies))
                or config['context']['query']['checkpoint_ply'] not in image_plies
                or config['context']['query']['checkpoint_ply'] >= image_plies[-1]):
            raise ValueError('history image checkpoint labels required')
    elif image_plies is not None:
        raise ValueError('checkpoint labels belong only to history tasks')
    sources = [Path(p).resolve(strict=True) for p in images]
    if any(not p.is_file() or p.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'} for p in sources):
        raise ValueError('raster image files required')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    files, refs = {}, []
    for i, path in enumerate(sources, 1):
        name = f'image-{i:03d}{path.suffix.lower()}'
        raw = path.read_bytes()
        with (directory / name).open('xb') as f:
            f.write(raw)
        files[name] = digest(raw)
        reference = {'path': str((directory / name).resolve()), 'sha256': files[name]}
        if image_plies is not None:
            reference['ply'] = image_plies[i - 1]
        refs.append(reference)
    # A query sees only the current frame. Past files belong to a completed
    # exposure phase, not the query allowlist. Retained context remains allowed.
    packet = {'task': config['task'], 'images': refs[-1:] if config['task'] == 'history' else refs,
              'context': config['context']}
    if config['task'] == 'history':
        exposure = {'task': 'history_exposure', 'images': refs[:-1],
                    'orientation': config['context']['orientation'],
                    'instruction': 'Observe the ordered frames. A later turn asks about history; reply READY without opening other files.'}
        write_new(directory / 'exposure.json', exposure)
        files['exposure.json'] = digest((directory / 'exposure.json').read_bytes())
    write_new(directory / 'input.json', packet)
    files['input.json'] = digest((directory / 'input.json').read_bytes())
    manifest = {'config': config, 'files': files, 'source_sha256': digest(Path(__file__).read_bytes())}
    write_new(directory / 'manifest.json', manifest)
    return manifest


def verify(directory):
    directory = Path(directory).resolve(strict=True)
    manifest = strict_json((directory / 'manifest.json').read_bytes())
    validate_config(manifest['config'])
    if manifest['source_sha256'] != digest(Path(__file__).read_bytes()):
        raise ValueError('submission mechanics changed')
    for name, expected in manifest['files'].items():
        path = (directory / name).resolve(strict=True)
        if Path(name).is_absolute() or not path.is_relative_to(directory) or digest(path.read_bytes()) != expected:
            raise ValueError('frozen player input changed or escapes trial')
    return manifest


def record_exposure(directory, actor_thread_id, completed_turn_id, evidence_file):
    """Pin controller-verified exposure proof; actual host auditing is mandatory."""
    directory = Path(directory)
    manifest = verify(directory)
    if manifest['config']['task'] != 'history':
        raise ValueError('exposure phase belongs only to history tasks')
    if any(not isinstance(v, str) or not v.strip() for v in [actor_thread_id, completed_turn_id]):
        raise ValueError('actual actor and completed exposure turn required')
    evidence = Path(evidence_file).resolve(strict=True)
    if not evidence.is_file():
        raise ValueError('immutable host proof file required')
    receipt = {'actor_thread_id': actor_thread_id, 'completed_turn_id': completed_turn_id,
               'evidence_path': str(evidence), 'evidence_sha256': digest(evidence.read_bytes()),
               'manifest_sha256': digest((directory / 'manifest.json').read_bytes()),
               'recorded_at': now().isoformat()}
    write_new(directory / 'exposure-complete.json', receipt)
    return receipt


def exposure_receipt(directory, manifest, actor_thread_id):
    receipt = strict_json((directory / 'exposure-complete.json').read_bytes())
    if (not actor_thread_id or receipt['actor_thread_id'] != actor_thread_id
            or receipt['manifest_sha256'] != digest((directory / 'manifest.json').read_bytes())
            or digest(Path(receipt['evidence_path']).read_bytes()) != receipt['evidence_sha256']):
        raise ValueError('same actor and unchanged exposure proof required')
    return receipt


def launch(directory, *, actor_thread_id=None):
    directory = Path(directory)
    config = verify(directory)['config']
    opened = now()
    clock = {'opened_at': opened.isoformat(),
             'deadline': (opened + timedelta(seconds=config['seconds'])).isoformat(),
             'manifest_sha256': digest((directory / 'manifest.json').read_bytes())}
    if config['task'] == 'history':
        exposure_receipt(directory, verify(directory), actor_thread_id)
        clock['actor_thread_id'] = actor_thread_id
        clock['exposure_sha256'] = digest((directory / 'exposure-complete.json').read_bytes())
    elif actor_thread_id is not None:
        raise ValueError('explicit staged actor binding belongs only to history tasks')
    write_new(directory / 'clock.json', clock)
    return clock


def response_format(value, config):
    if not isinstance(value, dict):
        return False
    task = config['task']
    if task == 'history':
        return set(value) == {'recall'} and piece_map(value['recall'], config['context']['query']['squares'])
    if task == 'perception':
        return (set(value) == {'move', 'piece_map'} and move_format(value['move'])
                and piece_map(value['piece_map'], SQUARES))
    return set(value) == {'move'} and move_format(value['move'])


def submit(directory, raw):
    directory = Path(directory)
    manifest = verify(directory)
    clock = strict_json((directory / 'clock.json').read_bytes())
    expected = {'opened_at', 'deadline', 'manifest_sha256'}
    if manifest['config']['task'] == 'history':
        expected |= {'actor_thread_id', 'exposure_sha256'}
        exposure_receipt(directory, manifest, clock.get('actor_thread_id'))
        if clock.get('exposure_sha256') != digest((directory / 'exposure-complete.json').read_bytes()):
            raise ValueError('exposure receipt changed')
    if set(clock) != expected or clock['manifest_sha256'] != digest((directory / 'manifest.json').read_bytes()):
        raise ValueError('launched manifest changed')
    received = now()
    start, deadline = [datetime.fromisoformat(clock[k]) for k in ['opened_at', 'deadline']]
    if (start.tzinfo is None or deadline.tzinfo is None or received < start
            or deadline != start + timedelta(seconds=manifest['config']['seconds'])):
        raise ValueError('invalid clock provenance')
    if len(raw) > 65536:
        raise ValueError('response exceeds bounded payload size')
    try:
        parsed = strict_json(raw)
        valid = bool(response_format(parsed, manifest['config']))
    except (ValueError, UnicodeError, TypeError):
        parsed, valid = None, False
    result = {'received_at': received.isoformat(), 'late': received >= deadline,
              'format_valid': valid, 'response': parsed if valid else None,
              'raw_base64': base64.b64encode(raw).decode(), 'raw_sha256': digest(raw),
              'clock_sha256': digest((directory / 'clock.json').read_bytes())}
    write_new(directory / 'response.json', result)
    return {k: result[k] for k in ['received_at', 'late', 'format_valid', 'raw_sha256']}


def read_result(directory):
    """Audit saved bytes/timing without reading evaluator truth or scoring chess."""
    directory = Path(directory)
    manifest = verify(directory)
    clock = strict_json((directory / 'clock.json').read_bytes())
    record = strict_json((directory / 'response.json').read_bytes())
    fields = {'received_at', 'late', 'format_valid', 'response', 'raw_base64',
              'raw_sha256', 'clock_sha256'}
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError('invalid response record')
    if (clock['manifest_sha256'] != digest((directory / 'manifest.json').read_bytes())
            or record['clock_sha256'] != digest((directory / 'clock.json').read_bytes())):
        raise ValueError('clock or manifest commitment changed')
    if manifest['config']['task'] == 'history':
        exposure_receipt(directory, manifest, clock.get('actor_thread_id'))
        if clock.get('exposure_sha256') != digest((directory / 'exposure-complete.json').read_bytes()):
            raise ValueError('exposure receipt changed')
    start, deadline, received = [datetime.fromisoformat(x) for x in
                                [clock['opened_at'], clock['deadline'], record['received_at']]]
    if (any(x.tzinfo is None for x in [start, deadline, received]) or received < start
            or deadline != start + timedelta(seconds=manifest['config']['seconds'])
            or type(record['late']) is not bool or record['late'] != (received >= deadline)):
        raise ValueError('response timing differs from clock')
    raw = base64.b64decode(record['raw_base64'], validate=True)
    if len(raw) > 65536 or digest(raw) != record['raw_sha256']:
        raise ValueError('raw response commitment changed')
    try:
        parsed = strict_json(raw)
        valid = bool(response_format(parsed, manifest['config']))
    except (ValueError, UnicodeError, TypeError):
        parsed, valid = None, False
    if (type(record['format_valid']) is not bool or record['format_valid'] != valid
            or record['response'] != (parsed if valid else None)):
        raise ValueError('response differs from preserved bytes')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['launch', 'submit', 'verify'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('--actor-thread-id', help='required for a staged history query launch')
    args = parser.parse_args()
    result = (launch(args.directory, actor_thread_id=args.actor_thread_id) if args.action == 'launch' else
              submit(args.directory, sys.stdin.buffer.read(65537)) if args.action == 'submit' else
              {'verified': True, 'files': list(verify(args.directory)['files'])})
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

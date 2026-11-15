"""File-based supplementary trials, isolated from native-game collection."""
import argparse
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

ARMS = frozenset('ABCDEFGHI')
STATE = frozenset('BDEFG')
LEGALITY = frozenset('CDEFG')
SQUARES = frozenset(f'{file}{rank}' for file in 'abcdefgh' for rank in '12345678')
ACTOR_SECONDS = 90


def now():
    return datetime.now(timezone.utc)


def write_new(path, value):
    serialized = json.dumps(value, indent=2, allow_nan=False) + '\n'
    with path.open('x') as stream:
        stream.write(serialized)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def item_state(corpus, item_id):
    items = json.loads((corpus / 'evaluator/items.json').read_text())['items']
    matching = [item for item in items if item['item_id'] == item_id]
    if len(matching) != 1:
        raise ValueError('expected one corpus item')
    return matching[0]


def prepare(corpus, item_id, arm, output, *, supplement=None, engine=None):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'preparation.json', {'started_at': now().isoformat(), 'arm': arm,
                                          'item_id': item_id, 'source_sha256': sha(Path(__file__))})
    try:
        return _prepare(corpus, item_id, arm, output, supplement=supplement, engine=engine)
    except BaseException as exc:
        write_new(output / 'preparation-failure.json', {'failed_at': now().isoformat(),
                  'error_type': type(exc).__name__, 'note': 'Preserve failed preparation; no automatic retry'})
        raise


async def bounded_recommendation(board, engine_path):
    import chess
    import chess.engine
    transport = worker = None
    async def perform():
        nonlocal transport, worker
        transport, worker = await chess.engine.popen_uci(str(engine_path))
        if 'Stockfish' not in worker.id.get('name', ''):
            raise ValueError('Stockfish is required')
        options = {'Threads': 1, 'Hash': 16, 'UCI_LimitStrength': False,
                   'Skill Level': 20, 'SyzygyPath': '', 'Clear Hash': None}
        await worker.configure(options)
        info = await worker.analyse(board, chess.engine.Limit(nodes=2000), game=object())
        return ({'move': info['pv'][0].uci(), 'nodes': info['nodes'], 'seconds': info.get('time')},
                {'binary_sha256': sha(engine_path), 'engine_id': worker.id,
                 'nominal_nodes': 2000, 'threads': 1, 'hash_mb': 16,
                 'query_timeout_seconds': 10, 'cleanup_timeout_seconds': 3})
    try:
        return await asyncio.wait_for(perform(), 10)
    finally:
        try:
            if worker is not None:
                try:
                    await asyncio.wait_for(worker.quit(), 3)
                except (TimeoutError, chess.engine.EngineError):
                    pass
        finally:
            if transport is not None:
                transport.close()


def _prepare(corpus, item_id, arm, output, *, supplement=None, engine=None):
    import chess
    import chess.engine
    started = now()
    corpus = corpus.resolve(strict=True)
    item = item_state(corpus, item_id)
    player_path = corpus / item['player_path']
    player = json.loads(player_path.read_text())
    image = corpus / player['image']['path']
    if sha(image) != player['image']['sha256']:
        raise ValueError('image hash mismatch')
    board = chess.Board(item['fen'])
    if not board.is_valid() or board.is_game_over():
        raise ValueError('invalid or terminal trial position')
    if (arm in {'H', 'I'}) != (supplement is not None):
        raise ValueError('lesson/sham supplement required only for H/I')
    attachment = {}
    if arm in STATE:
        attachment['occupancy'] = item['occupancy']
    reasoning = 'low' if arm == 'E' else 'high'
    allocation = None
    if arm == 'F':
        allocation = {'in_check': board.is_check(), 'legal_moves': board.legal_moves.count(),
                      'pieces': len(board.piece_map())}
        reasoning = ('high' if allocation['in_check'] or allocation['legal_moves'] <= 10
                     or allocation['pieces'] <= 12 else 'low')
    search = None
    if arm == 'G':
        if engine is None:
            raise ValueError('bounded-search arm requires engine path')
        engine = engine.resolve(strict=True)
        from .engine_budget import engine_allowance
        with engine_allowance(corpus, str(output.resolve()), reserve_seconds=13):
            attachment['bounded_search'], search = asyncio.run(bounded_recommendation(board, engine))
    if supplement is not None:
        attachment['supplement'] = supplement.read_text()
    write_new(output / 'attachment.json', attachment)
    prepared = now()
    manifest = {'schema_version': 1, 'item_id': item_id, 'arm': arm,
                'corpus': str(corpus), 'corpus_manifest_sha256': sha(corpus / 'manifest.json'),
                'evaluator_items_sha256': sha(corpus / 'evaluator/items.json'),
                'player_path': str(player_path), 'player_sha256': sha(player_path),
                'image_path': str(image), 'image_sha256': sha(image),
                'attachment_sha256': sha(output / 'attachment.json'),
                'supplement_sha256': sha(supplement) if supplement else None,
                'preparation_started': started.isoformat(), 'prepared_at': prepared.isoformat(),
                'actor_seconds': ACTOR_SECONDS,
                'deadline_semantics': 'final submission within90s of controller dispatch request; explicit launch required',
                'desired_model': 'gpt-6.1-sol', 'desired_reasoning': reasoning,
                'adaptive_allocation': allocation, 'search': search,
                'source_sha256': sha(Path(__file__))}
    write_new(output / 'manifest.json', manifest)
    return manifest


def launch(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    verify_inputs(directory, manifest)
    dispatched = now()
    record = {'dispatch_requested_at': dispatched.isoformat(),
              'deadline': (dispatched + timedelta(seconds=manifest['actor_seconds'])).isoformat(),
              'manifest_sha256': sha(directory / 'manifest.json'),
              'note': 'Controller calls immediately before fresh actor dispatch; actual host creation audited separately'}
    write_new(directory / 'launch.json', record)
    return record


def verify_inputs(directory, manifest):
    paths = [(Path(manifest['corpus']) / 'manifest.json', 'corpus_manifest_sha256'),
             (Path(manifest['corpus']) / 'evaluator/items.json', 'evaluator_items_sha256'),
             (Path(manifest['player_path']), 'player_sha256'),
             (Path(manifest['image_path']), 'image_sha256'),
             (directory / 'attachment.json', 'attachment_sha256'),
             (Path(__file__), 'source_sha256')]
    for path, key in paths:
        if sha(path) != manifest[key]:
            raise ValueError('prepared input or mechanics changed: ' + key)


def validate_response(value):
    if not isinstance(value, dict) or set(value) != {'move', 'piece_map', 'side_to_move', 'confidence',
                                                   'castling', 'en_passant_square'}:
        raise ValueError('response requires move, piece_map, side_to_move, confidence, castling and en_passant_square')
    if not isinstance(value['move'], str) or not re.fullmatch('[a-h][1-8][a-h][1-8][qrbn]?', value['move']):
        raise ValueError('move must be UCI coordinate notation')
    pieces = value['piece_map']
    if (not isinstance(pieces, dict) or set(pieces) != SQUARES
            or any(not isinstance(p, str) or p not in set('PNBRQKpnbrqk.?') for p in pieces.values())):
        raise ValueError('piece_map requires all64 squares with piece symbol, dot or question mark')
    if value['side_to_move'] not in {'white', 'black', 'unknown'}:
        raise ValueError('unknown side_to_move value')
    if type(value['confidence']) not in {int, float} or not 0 <= value['confidence'] <= 1:
        raise ValueError('confidence must lie in0..1')
    rights = value['castling']
    if not isinstance(rights, dict) or set(rights) != {'white', 'black'}:
        raise ValueError('castling requires both colors')
    for flags in rights.values():
        if not isinstance(flags, dict) or set(flags) != {'kingside', 'queenside'}:
            raise ValueError('castling requires kingside and queenside')
        if any(type(flag) is not bool and flag != 'unknown' for flag in flags.values()):
            raise ValueError('castling rights must be boolean or unknown')
    ep = value['en_passant_square']
    if ep is not None and (not isinstance(ep, str) or ep not in SQUARES | {'unknown'}):
        raise ValueError('en_passant_square must be square, null or unknown')


def submit(directory, stage, response_path):
    """Persist the first submission, even malformed/late; disclose only assigned feedback."""
    if stage not in {'initial', 'final'}:
        raise ValueError('unknown submission stage')
    manifest = json.loads((directory / 'manifest.json').read_text())
    launched = json.loads((directory / 'launch.json').read_text())
    if sha(directory / 'manifest.json') != launched['manifest_sha256']:
        raise ValueError('trial manifest changed after launch')
    verify_inputs(directory, manifest)
    corpus = Path(manifest['corpus'])
    if stage == 'final' and not (directory / 'initial.json').exists():
        raise ValueError('initial submission required before final')
    if stage == 'initial' and (directory / 'final.json').exists():
        raise ValueError('final already submitted')
    raw = response_path.read_bytes()
    received = now()
    late = received >= datetime.fromisoformat(launched['deadline'])
    error = None
    value = None
    try:
        def reject_constant(token):
            raise ValueError('nonfinite JSON constant')
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('duplicate JSON key')
                value[key] = item
            return value
        value = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)
        validate_response(value)
    except (ValueError, TypeError) as exc:
        error = str(exc)
        value = None
    verdict = None
    if error is None and stage == 'initial' and manifest['arm'] in LEGALITY and not late:
        import chess
        board = chess.Board(item_state(corpus, manifest['item_id'])['fen'])
        try:
            legal = chess.Move.from_uci(value['move']) in board.legal_moves
        except ValueError:
            legal = False
        verdict = 'legal' if legal else 'illegal'
    record = {'received_at': received.isoformat(), 'late': late, 'validation_error': error,
              'response': value, 'raw_utf8': raw.decode('utf-8', errors='replace'),
              'raw_base64': base64.b64encode(raw).decode('ascii'),
              'response_sha256': hashlib.sha256(raw).hexdigest(), 'feedback': verdict}
    write_new(directory / f'{stage}.json', record)
    # No state, score, legal-move list or recommendation is returned here.
    return {'recorded': stage, 'late': late, 'format_valid': error is None,
            **({'verdict': verdict} if verdict else {})}


def transcription_score(response, occupancy):
    validate_response(response)
    correct = sum(response['piece_map'][square] == occupancy.get(square, '.') for square in SQUARES)
    return {'correct_squares': correct, 'total_squares': 64, 'exact_board': correct == 64,
            'unknown_squares': sum(p == '?' for p in response['piece_map'].values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('prepare')
    start.add_argument('corpus', type=Path)
    start.add_argument('item_id')
    start.add_argument('arm', choices=sorted(ARMS))
    start.add_argument('output', type=Path)
    start.add_argument('--supplement', type=Path)
    start.add_argument('--engine', type=Path)
    response = commands.add_parser('submit')
    response.add_argument('directory', type=Path)
    response.add_argument('stage', choices=['initial', 'final'])
    response.add_argument('response', type=Path)
    dispatch = commands.add_parser('launch')
    dispatch.add_argument('directory', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.corpus, args.item_id, args.arm, args.output,
                         supplement=args.supplement, engine=args.engine)
    elif args.command == 'submit':
        result = submit(args.directory, args.stage, args.response)
    else:
        result = launch(args.directory)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

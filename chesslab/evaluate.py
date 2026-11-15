"""Offline PGN and engine audit. Never import this module into a player context."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

import chess
import chess.engine

RESULTS = {'1-0', '0-1', '1/2-1/2', '*'}
HEADER = re.compile(r'\[([A-Za-z0-9_]+)\s+("(?:[^"\\]|\\["\\])*")\s*\]')
MOVE_NUMBER = re.compile(r'(\d+)\.(\.\.)?')
SHA256 = re.compile(r'[0-9a-f]{64}')


@dataclass
class ParsedGame:
    headers: dict[str, str]
    initial: chess.Board
    moves: list[chess.Move]
    final: chess.Board


def _tokens(body: str):
    """Tokenize the supported mainline subset; never silently discard garbage."""
    pos = 0
    while pos < len(body):
        if body[pos].isspace():
            pos += 1
        elif body[pos] == '{':
            end = body.find('}', pos + 1)
            if end < 0 or '{' in body[pos + 1:end]:
                raise ValueError('unclosed or nested PGN comment')
            pos = end + 1
        elif body[pos] == ';':
            end = body.find('\n', pos)
            pos = len(body) if end < 0 else end + 1
        elif body[pos] in '()[]}' or body.startswith('%', pos):
            raise ValueError('unsupported variation, extra game header, or PGN token')
        else:
            number = MOVE_NUMBER.match(body, pos)
            if number:
                yield number.group()
                pos = number.end()
                continue
            end = pos
            while end < len(body) and not body[end].isspace() and body[end] not in '{};()[]':
                end += 1
            yield body[pos:end]
            pos = end


def parse_game(text: str, *, max_plies: int = 400) -> ParsedGame:
    """Read one standard-chess mainline, with explicit header and movetext result.

    Variations are rejected rather than scored accidentally. Non-board endings
    such as resignation remain header-only claims; require independent UI evidence.
    """
    if type(max_plies) is not int or max_plies < 1:
        raise ValueError('max_plies must be a positive integer')
    text = text.lstrip('\ufeff').strip()
    headers: dict[str, str] = {}
    pos = 0
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos == len(text) or text[pos] != '[':
            break
        match = HEADER.match(text, pos)
        if not match:
            raise ValueError('malformed PGN header')
        key, value = match.groups()
        if key in headers:
            raise ValueError('duplicate PGN header')
        headers[key] = json.loads(value)
        pos = match.end()
    if headers.get('Result') not in RESULTS:
        raise ValueError('missing or invalid Result header')
    if headers.get('Variant', 'Standard') not in {'Standard', 'Chess'}:
        raise ValueError('only standard chess is supported')
    if ('FEN' in headers) != (headers.get('SetUp') == '1'):
        raise ValueError('FEN requires SetUp=1 and conversely')
    if 'SetUp' in headers and headers['SetUp'] not in {'0', '1'}:
        raise ValueError('invalid SetUp header')
    initial = chess.Board(headers.get('FEN', chess.STARTING_FEN))
    if not initial.is_valid():
        raise ValueError('invalid starting board')
    board = initial.copy()
    moves: list[chess.Move] = []
    ending = None
    for token in _tokens(text[pos:]):
        if ending is not None:
            raise ValueError('content after movetext result; expected one game')
        if token in RESULTS:
            ending = token
            continue
        if token.startswith('$') and token[1:].isdigit():
            continue
        if token in {'!', '?', '!!', '??', '!?', '?!'}:
            continue
        number = MOVE_NUMBER.fullmatch(token)
        if number:
            if int(number[1]) != board.fullmove_number:
                raise ValueError('move number disagrees with board')
            if bool(number[2]) != (board.turn == chess.BLACK):
                raise ValueError('move-number side disagrees with board')
            continue
        if board.is_game_over():
            raise ValueError('move after board-terminal position')
        if len(moves) >= max_plies:
            raise ValueError('game exceeds max_plies bound')
        san = token.rstrip('!?')
        try:
            move = board.parse_san(san)
        except ValueError as exc:
            raise ValueError(f'invalid or illegal SAN at ply {len(moves)+1}: {token}') from exc
        if not move or move not in board.legal_moves:
            raise ValueError('null or illegal move')
        expected_check, expected_mate = san.endswith('+'), san.endswith('#')
        moves.append(move)
        board.push(move)
        if expected_mate and not board.is_checkmate():
            raise ValueError('false mate marker in SAN')
        if expected_check and not board.is_check():
            raise ValueError('false check marker in SAN')
    if ending is None:
        raise ValueError('missing movetext result')
    if ending != headers['Result']:
        raise ValueError('movetext result disagrees with Result header')
    outcome = board.outcome(claim_draw=False)
    if outcome is not None and outcome.result() != ending:
        raise ValueError('board-terminal result disagrees with PGN result')
    return ParsedGame(headers, initial, moves, board)


def audit_actions(path: Path) -> dict:
    """Verify referenced screenshot bytes; this does not verify their meaning."""
    path = path.resolve(strict=True)
    root = path.parent
    references = []
    seen: dict[str, str] = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'action line {number} must be an object')
        for key in ('pre', 'post', 'evidence'):
            if key not in row:
                continue
            ref = row[key]
            if (not isinstance(ref, dict) or not isinstance(ref.get('file'), str)
                    or not isinstance(ref.get('sha256'), str)
                    or not SHA256.fullmatch(ref['sha256'])):
                raise ValueError(f'invalid screenshot reference on line {number}')
            filename = Path(ref['file'])
            if filename.is_absolute():
                raise ValueError('screenshot paths must be relative')
            target = (root / filename).resolve(strict=True)
            if not target.is_relative_to(root) or not target.is_file():
                raise ValueError('screenshot path escapes evidence directory')
            if file_hash(target) != ref['sha256']:
                raise ValueError(f'screenshot hash mismatch: {ref["file"]}')
            if ref['file'] in seen and seen[ref['file']] != ref['sha256']:
                raise ValueError('conflicting hashes for screenshot')
            seen[ref['file']] = ref['sha256']
            references.append({'line': number, 'field': key, **ref})
    if not references:
        raise ValueError('actions file contains no screenshot references')
    return {'actions_sha256': file_hash(path), 'references_verified': len(references),
            'unique_files_verified': len(seen), 'visual_consistency_verified': False,
            'references': references}


def file_hash(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def score_record(info: dict, turn: chess.Color) -> dict:
    if 'score' not in info or 'pv' not in info or not info['pv']:
        raise ValueError('engine omitted score or principal variation')
    score = info['score'].pov(turn)
    return {'cp': score.score(), 'mate': score.mate(),
            'pv': [move.uci() for move in info['pv']],
            'nodes': info.get('nodes'), 'depth': info.get('depth'),
            'seldepth': info.get('seldepth'), 'time': info.get('time'),
            'lowerbound': bool(info.get('lowerbound', False)),
            'upperbound': bool(info.get('upperbound', False))}


async def analyse_game(game: ParsedGame, engine_path: Path, *, nodes: int,
                       hash_mb: int, timeout: float, total_timeout: float) -> dict:
    """Two fresh searches per ply at the identical root and side-to-move POV."""
    if type(nodes) is not int or not 1 <= nodes <= 10_000_000:
        raise ValueError('nodes must be an integer in 1..10000000')
    if type(hash_mb) is not int or not 1 <= hash_mb <= 1024:
        raise ValueError('hash_mb must be an integer in 1..1024')
    if not 0 < timeout <= 300 or not 0 < total_timeout <= 3600:
        raise ValueError('timeouts must be positive and bounded')
    engine_path = engine_path.resolve(strict=True)
    engine_sha = file_hash(engine_path)

    async def perform() -> dict:
        transport, engine = await asyncio.wait_for(
            chess.engine.popen_uci(str(engine_path)), timeout)
        try:
            if 'Stockfish' not in engine.id.get('name', ''):
                raise ValueError('this protocol currently supports Stockfish only')
            desired = {'Threads': 1, 'Hash': hash_mb, 'UCI_LimitStrength': False,
                       'Skill Level': 20, 'SyzygyPath': ''}
            if not {'Threads', 'Hash', 'Clear Hash'} <= engine.options.keys():
                raise ValueError('engine lacks required reproducibility options')
            options = {name: value for name, value in desired.items() if name in engine.options}
            await asyncio.wait_for(engine.configure(options), timeout)
            rows = []
            board = game.initial.copy()
            for ply, move in enumerate(game.moves, 1):
                base = {'ply': ply, 'turn': 'white' if board.turn else 'black',
                        'fen': board.fen(), 'move': move.uci(), 'san': board.san(move)}
                analyses = []
                for root_moves in (None, [move]):
                    # A new game ID plus explicit Clear Hash prevents cross-search
                    # transposition-table reuse from favoring the second query.
                    await asyncio.wait_for(engine.configure({'Clear Hash': None}), timeout)
                    info = await asyncio.wait_for(engine.analyse(
                        board, chess.engine.Limit(nodes=nodes), game=object(),
                        root_moves=root_moves, info=chess.engine.INFO_ALL), timeout)
                    analyses.append(score_record(info, board.turn))
                best, selected = analyses
                delta = (best['cp'] - selected['cp']
                         if (best['cp'] is not None and selected['cp'] is not None
                             and not any(r[k] for r in analyses
                                         for k in ('lowerbound', 'upperbound'))) else None)
                rows.append({**base, 'best': best, 'selected': selected,
                             'cp_loss_raw': delta,
                             'cp_loss_nonnegative': max(0, delta) if delta is not None else None,
                             'bounded_search_inversion': delta < 0 if delta is not None else None})
                board.push(move)
            return {'engine_id': engine.id, 'binary_sha256': engine_sha,
                    'option_defaults': {key: value.default for key, value in engine.options.items()},
                    'options': options, 'nodes_per_search': nodes,
                    'searches_per_ply': 2, 'hash_reset_each_search': True,
                    'analysis_timeout_seconds': timeout,
                    'total_timeout_seconds': total_timeout,
                    'rows': rows}
        finally:
            try:
                await asyncio.wait_for(engine.quit(), min(timeout, 5))
            except (asyncio.TimeoutError, chess.engine.EngineError):
                pass
            finally:
                transport.close()

    return await asyncio.wait_for(perform(), total_timeout)


def evaluate(pgn: Path, *, engine: Path | None = None, nodes: int = 10_000,
             hash_mb: int = 16, timeout: float = 30, total_timeout: float = 600,
             actions: Path | None = None, require_board_terminal: bool = False) -> dict:
    raw = pgn.read_bytes()
    game = parse_game(raw.decode('utf-8-sig'))
    outcome = game.final.outcome(claim_draw=False)
    if require_board_terminal and outcome is None:
        raise ValueError('board is not terminal; external ending needs independent evidence')
    result = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
              'pgn_sha256': hashlib.sha256(raw).hexdigest(), 'chess_version': chess.__version__,
              'plies': len(game.moves), 'result_header': game.headers['Result'],
              'board_terminal': outcome is not None,
              'board_result': outcome.result() if outcome else None,
              'termination': outcome.termination.name if outcome else None,
              'checkmate': game.final.is_checkmate(), 'final_fen': game.final.fen(),
              'rating': None, 'warning': 'Post-game evidence only; no model-strength inference.'}
    if actions:
        result['screenshots'] = audit_actions(actions)
    if engine:
        started = time.monotonic()
        result['engine_analysis'] = asyncio.run(analyse_game(
            game, engine, nodes=nodes, hash_mb=hash_mb,
            timeout=timeout, total_timeout=total_timeout))
        result['engine_analysis']['elapsed_seconds'] = time.monotonic() - started
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pgn', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--engine', type=Path)
    parser.add_argument('--nodes', type=int, default=10_000)
    parser.add_argument('--hash-mb', type=int, default=16)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--total-timeout', type=float, default=600)
    parser.add_argument('--actions', type=Path)
    parser.add_argument('--require-board-terminal', action='store_true')
    args = parser.parse_args()
    try:
        result = evaluate(args.pgn, engine=args.engine, nodes=args.nodes,
                          hash_mb=args.hash_mb, timeout=args.timeout,
                          total_timeout=args.total_timeout, actions=args.actions,
                          require_board_terminal=args.require_board_terminal)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # A new path avoids overwriting an earlier analysis or its source evidence.
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except (ValueError, OSError, asyncio.TimeoutError, chess.engine.EngineError) as exc:
        parser.exit(2, f'evaluation failed: {exc}\n')
    print(f'Verified {result["plies"]} legal plies; board_terminal={result["board_terminal"]}.')


if __name__ == '__main__':
    main()

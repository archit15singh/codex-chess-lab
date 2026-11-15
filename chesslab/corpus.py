"""Offline, evaluator-owned corpus construction; never import into a player context."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import subprocess
import sys
import time

import chess
import chess.engine
import chess.pgn
import chess.svg

GENERATION_SEED = 2026111502
SCHEDULE_SEED = 2026111503
BOOTSTRAP_SEED = 2026111504
TOTAL_PLIES = 40
MAX_CANDIDATES = 10
NODES = 1000
OPTIONS = {'Threads': 1, 'Hash': 16, 'UCI_LimitStrength': False,
           'Skill Level': 20, 'SyzygyPath': ''}


@dataclass(frozen=True)
class Family:
    name: str
    split: str
    prefix: tuple[str, ...]


FAMILIES = tuple(Family(name, split, tuple(prefix.split())) for name, split, prefix in [
    ('italian', 'training', 'e2e4 e7e5 g1f3 b8c6 f1c4'),
    ('spanish', 'training', 'e2e4 e7e5 g1f3 b8c6 f1b5'),
    ('early-queen', 'training', 'e2e4 e7e5 d1h5'),
    ('queens-gambit', 'development', 'd2d4 d7d5 c2c4'),
    ('kings-indian', 'development', 'd2d4 g8f6 c2c4 g7g6 b1c3 f8g7'),
    ('english', 'development', 'c2c4 e7e5 b1c3'),
    ('sicilian', 'final', 'e2e4 c7c5'),
    ('french', 'final', 'e2e4 e7e6 d2d4 d7d5'),
    ('caro-kann', 'final', 'e2e4 c7c6 d2d4 d7d5'),
    ('scandinavian', 'final', 'e2e4 d7d5'),
    ('alekhine', 'final', 'e2e4 g8f6'),
    ('pirc', 'final', 'e2e4 d7d6 d2d4 g8f6 b1c3 g7g6'),
])


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(board: chess.Board) -> str:
    """First four FEN fields, including only a legally available EP square."""
    return ' '.join(board.fen(en_passant='legal').split()[:4])


def candidate_seed(master: int, family: str, attempt: int) -> int:
    return int.from_bytes(hashlib.sha256(f'{master}:{family}:{attempt}'.encode()).digest()[:8], 'big')


def checkpoints(family: Family) -> tuple[int, ...]:
    return (15, 24, 31, 40) if family.split == 'final' else (15, 40)


def orientation(family: Family, ply: int) -> chess.Color:
    return ply in (15, 40) if family.split == 'final' else ply == 15


def common_rules(board: chess.Board) -> dict:
    return {'side_to_move': 'white' if board.turn else 'black',
            'castling': {name: {'kingside': board.has_kingside_castling_rights(color),
                               'queenside': board.has_queenside_castling_rights(color)}
                         for name, color in [('white', chess.WHITE), ('black', chess.BLACK)]},
            'en_passant_square': chess.square_name(board.ep_square)
            if board.has_legal_en_passant() else None,
            'halfmove_clock': board.halfmove_clock}


def player_item(item_id: str, board: chess.Board, image: dict, facing: chess.Color) -> dict:
    return {'schema_version': 1, 'item_id': item_id, 'image': image,
            'orientation': 'white' if facing else 'black', 'rules': common_rules(board)}


def render(board: chess.Board, facing: chess.Color) -> tuple[bytes, str]:
    """Return PNG and deterministic SVG hash; no annotations or move hints."""
    import pymupdf
    svg = chess.svg.board(board, orientation=facing, coordinates=True, size=390,
                          check=None, lastmove=None, arrows=[]).encode()
    with pymupdf.open(stream=svg, filetype='svg') as document:
        png = document[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).tobytes('png')
    return png, digest(svg)


class GeneratorEngine:
    """Bounded serial Stockfish queries; no persistent hash between positions."""
    def __init__(self, path: Path, total_seconds: float = 1800):
        self.path = path.resolve(strict=True)
        self.elapsed = 0.0
        self.total_seconds = total_seconds
        self.transport = self.protocol = None
        self.metadata = {}

    async def bounded(self, awaitable):
        remaining = self.total_seconds - self.elapsed
        if remaining <= 0:
            awaitable.close()
            raise TimeoutError('generator engine-work budget exhausted')
        started = time.monotonic()
        try:
            return await asyncio.wait_for(awaitable, min(3.0, remaining))
        finally:
            self.elapsed += time.monotonic() - started

    async def __aenter__(self):
        self.transport, self.protocol = await self.bounded(chess.engine.popen_uci(str(self.path)))
        try:
            if 'Stockfish' not in self.protocol.id.get('name', ''):
                raise ValueError('Stockfish is required')
            required = set(OPTIONS) | {'Clear Hash', 'MultiPV'}
            if not required <= self.protocol.options.keys():
                raise ValueError('engine lacks required options')
            await self.bounded(self.protocol.configure(OPTIONS))
            self.metadata = {'engine_id': self.protocol.id, 'binary_path': str(self.path),
                             'binary_sha256': digest(self.path.read_bytes()),
                             'option_defaults': {k: v.default for k, v in self.protocol.options.items()},
                             'options': OPTIONS, 'nodes_per_query': NODES, 'multipv': 3,
                             'clear_hash_each_query': True, 'query_timeout_seconds': 3,
                             'total_engine_work_seconds': self.total_seconds}
            return self
        except BaseException:
            self.transport.close()
            raise

    async def __aexit__(self, *_):
        try:
            await asyncio.wait_for(self.protocol.quit(), 3)
        except (TimeoutError, chess.engine.EngineError):
            pass
        finally:
            self.transport.close()

    async def query(self, board: chess.Board) -> dict:
        started = time.monotonic()
        async def search():
            await self.protocol.configure({'Clear Hash': None})
            return await self.protocol.analyse(
                board, chess.engine.Limit(nodes=NODES), multipv=min(3, board.legal_moves.count()),
                game=object(), info=chess.engine.INFO_ALL)
        infos = await self.bounded(search())
        rows = []
        for info in infos:
            pv = info.get('pv', [])
            if not pv or pv[0] not in board.legal_moves:
                raise ValueError('engine returned missing or illegal candidate')
            rows.append({'move': pv[0].uci(), 'pv': [m.uci() for m in pv],
                         'nodes': info.get('nodes'), 'depth': info.get('depth'),
                         'time': info.get('time'), 'score': str(info.get('score')),
                         'lowerbound': info.get('lowerbound', False),
                         'upperbound': info.get('upperbound', False)})
        choices = sorted({row['move'] for row in rows})
        if not 1 <= len(choices) <= 3:
            raise ValueError('engine candidate count outside 1..3')
        return {'candidates': choices, 'rows': rows,
                'elapsed_seconds': time.monotonic() - started}


async def candidate(family: Family, seed: int, engine, emit) -> list[chess.Board]:
    rng = random.Random(seed)
    board = chess.Board()
    frames = [board.copy(stack=True)]
    for ply in range(1, TOTAL_PLIES + 1):
        if board.is_game_over(claim_draw=False):
            break
        query = None
        if ply <= len(family.prefix):
            policy = 'prefix'
            chosen = family.prefix[ply - 1]
        elif rng.random() < 0.8:
            policy = 'uniform-engine-top-3'
            emit({'kind': 'query-started', 'family_id': family.name, 'seed': seed,
                  'ply': ply, 'fen': board.fen(), 'requested_nodes': NODES})
            try:
                query = await engine.query(board.copy(stack=True))
            except BaseException as exc:
                emit({'kind': 'query-failed', 'family_id': family.name, 'seed': seed,
                      'ply': ply, 'error_type': type(exc).__name__, 'message': str(exc)})
                raise
            choices = sorted(set(query['candidates']))
            if not 1 <= len(choices) <= 3:
                raise ValueError('invalid candidate count')
            chosen = rng.choice(choices)
        else:
            policy = 'uniform-legal'
            chosen = rng.choice(sorted(move.uci() for move in board.legal_moves))
        move = chess.Move.from_uci(chosen)
        if move not in board.legal_moves:
            raise ValueError('generator selected illegal move')
        emit({'kind': 'move', 'family_id': family.name, 'seed': seed, 'ply': ply,
              'fen_before': board.fen(), 'policy': policy, 'query': query, 'move': chosen})
        board.push(move)
        frames.append(board.copy(stack=True))
    return frames


def rejection(frames: list[chess.Board], family: Family, seen: set[str]) -> str | None:
    if len(frames) != TOTAL_PLIES + 1 or frames[-1].is_game_over(claim_draw=False):
        return 'terminal-or-short-game'
    identities = [canonical(frames[ply]) for ply in checkpoints(family)]
    if len(set(identities)) != len(identities):
        return 'duplicate-within-family-checkpoint'
    if any(identity in seen for identity in identities):
        return 'duplicate-across-family-checkpoint'
    return None


def write_json(path: Path, value) -> None:
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def validate_families(families: tuple[Family, ...]) -> None:
    if len({f.name for f in families}) != len(families):
        raise ValueError('duplicate family name')
    for family in families:
        if family.split not in ('training', 'development', 'final'):
            raise ValueError('invalid split')
        if not family.name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in family.name):
            raise ValueError('unsafe family name')
        if len(family.prefix) >= TOTAL_PLIES:
            raise ValueError('prefix must leave a continuation')
        board = chess.Board()
        for uci in family.prefix:
            board.push_uci(uci)


async def build(output: Path, engine, *, source_commit: str, design_sha256: str,
                families: tuple[Family, ...] = FAMILIES, seed: int = GENERATION_SEED,
                renderer=render) -> dict:
    """Exclusive destination, bounded retries, durable partial trace on failure."""
    validate_families(families)
    output.mkdir(parents=False, exist_ok=False)
    for directory in ('images', 'player', 'evaluator', 'evaluator/games'):
        (output / directory).mkdir()
    seen: set[str] = set()
    image_refs, position_images = {}, {}
    items, games, sequences = [], [], []
    with (output / 'construction.jsonl').open('x') as log:
        def emit(record):
            log.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
            log.flush()

        def image(board, facing):
            identity = (canonical(board), facing)
            if identity in position_images:
                return position_images[identity]
            png, svg_hash = renderer(board, facing)
            if svg_hash not in image_refs:
                path = f'images/{svg_hash}.png'
                with (output / path).open('xb') as stream:
                    stream.write(png)
                image_refs[svg_hash] = {'path': path, 'sha256': digest(png)}
            elif image_refs[svg_hash]['sha256'] != digest(png):
                raise ValueError('renderer produced inconsistent bytes')
            position_images[identity] = image_refs[svg_hash]
            return image_refs[svg_hash]

        emit({'kind': 'start', 'source_commit': source_commit, 'design_sha256': design_sha256})
        try:
            for family in families:
                for attempt in range(1, MAX_CANDIDATES + 1):
                    selected_seed = candidate_seed(seed, family.name, attempt)
                    emit({'kind': 'candidate', 'family_id': family.name, 'attempt': attempt,
                          'seed': selected_seed})
                    frames = await candidate(family, selected_seed, engine, emit)
                    reason = rejection(frames, family, seen)
                    if reason is None:
                        break
                    emit({'kind': 'rejected', 'family_id': family.name, 'attempt': attempt,
                          'seed': selected_seed, 'reason': reason})
                else:
                    raise ValueError(f'candidate limit exhausted: {family.name}')
                seen.update(canonical(frames[ply]) for ply in checkpoints(family))
                emit({'kind': 'accepted', 'family_id': family.name, 'attempt': attempt,
                      'seed': selected_seed})
                frame_records = [{'ply': ply, 'fen': board.fen(), 'canonical_fen': canonical(board),
                                  'image': image(board, chess.WHITE), 'rules': common_rules(board)}
                                 for ply, board in enumerate(frames)]
                moves = [move.uci() for move in frames[-1].move_stack]
                for ply in checkpoints(family):
                    board, item_id = frames[ply], f'p{len(items) + 1:03d}'
                    player_path = f'player/{item_id}.json'
                    facing = orientation(family, ply)
                    write_json(output / player_path,
                               player_item(item_id, board, image(board, facing), facing))
                    items.append({'item_id': item_id, 'player_path': player_path,
                                  'family_id': family.name, 'split': family.split, 'ply': ply,
                                  'fen': board.fen(), 'canonical_fen': canonical(board),
                                  'history_uci': moves[:ply],
                                  'occupancy': {chess.square_name(s): p.symbol()
                                                for s, p in board.piece_map().items()}})
                game = chess.pgn.Game.from_board(frames[-1])
                game.headers.update({'Event': 'Offline generated corpus', 'White': 'Generator',
                                     'Black': 'Generator', 'Date': '????.??.??', 'Result': '*'})
                pgn_path = f'evaluator/games/{family.name}.pgn'
                with (output / pgn_path).open('x') as stream:
                    stream.write(str(game) + '\n')
                games.append({'family_id': family.name, 'split': family.split,
                              'seed': selected_seed, 'attempt': attempt, 'moves_uci': moves,
                              'prefix_uci': list(family.prefix), 'pgn_path': pgn_path,
                              'frames': frame_records})
                if family.split == 'final':
                    for length, probes in ((24, [6, 12, 18, 24]), (40, [10, 20, 30, 40])):
                        sequences.append({'sequence_id': f's{len(sequences) + 1:03d}',
                                          'orientation': 'white', 'initial_rules': common_rules(frames[0]),
                                          'checkpoints': probes,
                                          'frames': [{'ply': frame['ply'], 'image': frame['image']}
                                                     for frame in frame_records[:length + 1]]})
            write_json(output / 'evaluator/items.json', {'schema_version': 1, 'items': items})
            write_json(output / 'evaluator/families.json', {'schema_version': 1, 'families': games})
            write_json(output / 'player/sequences.json', {'schema_version': 1, 'sequences': sequences})
            emit({'kind': 'completed', 'items': len(items), 'families': len(games)})
        except BaseException as exc:
            emit({'kind': 'failed', 'error_type': type(exc).__name__, 'message': str(exc)})
            raise
    files = {str(path.relative_to(output)): digest(path.read_bytes())
             for path in sorted(output.rglob('*')) if path.is_file()}
    if len(files) + 1 > 750 or sum(p.is_dir() for p in output.rglob('*')) > 12:
        raise ValueError('corpus write bound exceeded')
    manifest = {'schema_version': 1, 'status': 'sealed', 'source_commit': source_commit,
                'design_sha256': design_sha256, 'generation_seed': seed,
                'schedule_seed': SCHEDULE_SEED, 'bootstrap_seed': BOOTSTRAP_SEED,
                'engine': engine.metadata, 'engine_work_seconds': engine.elapsed,
                'versions': {'python': sys.version, 'chess': chess.__version__,
                             'pymupdf': importlib.metadata.version('pymupdf')},
                'renderer': {'svg': 'chess.svg.board', 'size': 390, 'scale': 1.5,
                             'coordinates': True, 'hints': False,
                             'png_identity': 'filename is deterministic SVG SHA-256'},
                'policy': {'plies': TOTAL_PLIES, 'max_candidates': MAX_CANDIDATES,
                           'engine_branch_probability': 0.8, 'nodes': NODES,
                           'selection': 'uniform sorted unique UCI candidates or uniform sorted legal'},
                'families': [{'family_id': f.name, 'split': f.split, 'prefix_uci': list(f.prefix),
                              'checkpoints': checkpoints(f)} for f in families],
                'counts': {'items': len(items), 'families': len(games),
                           'sequences': len(sequences), 'images': len(image_refs)}, 'files': files}
    write_json(output / 'manifest.json', manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--design', required=True, type=Path)
    parser.add_argument('--design-sha256', required=True)
    args = parser.parse_args()
    try:
        source_root = Path(__file__).resolve().parents[1]
        output = args.output.resolve()
        if not output.is_relative_to(source_root / 'evidence/private'):
            raise ValueError('output must be below this checkout evidence/private')
        if output.exists():
            raise FileExistsError('output already exists')
        if digest(args.design.read_bytes()) != args.design_sha256:
            raise ValueError('design hash mismatch')
        if subprocess.check_output(['git', 'status', '--porcelain'], cwd=source_root, text=True).strip():
            raise ValueError('commit source changes before freezing a corpus')
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source_root, text=True).strip()
        async def run():
            async with GeneratorEngine(args.engine) as engine:
                return await build(output, engine, source_commit=commit,
                                   design_sha256=args.design_sha256)
        manifest = asyncio.run(run())
        print(json.dumps({'manifest': str(output / 'manifest.json'), 'counts': manifest['counts'],
                          'sha256': digest((output / 'manifest.json').read_bytes())}, sort_keys=True))
    except (ValueError, OSError, TimeoutError, chess.engine.EngineError) as exc:
        # Engine errors can contain a private FEN/PV. Preserve details only in
        # construction.jsonl, never echo them into a controller/player channel.
        print(f'corpus construction failed ({type(exc).__name__}); inspect private trace and inputs',
              file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()

"""Offline V2 diagnostic inputs from explicit legal histories; no model or engine.

The builder owns truth and player artifacts separately. Delivery must copy only
the condition's allowlisted files; this module is never a player tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

import chess
import chess.svg


SPLITS = {'pilot', 'training', 'development', 'final'}
TASKS = {'perception', 'history', 'correction', 'move'}
STYLES = {'plain', 'compact', 'angled', 'clutter'}
BASE = {'id', 'family', 'split', 'task', 'moves', 'orientation', 'style'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def position_hash(board):
    """Task-state identity ignores counters, retaining turn/rights/legal EP."""
    return digest(' '.join(board.fen(en_passant='legal').split()[:4]).encode())


def occupancy(board):
    return {chess.square_name(s): board.piece_at(s).symbol()
            if board.piece_at(s) else '.' for s in chess.SQUARES}


def history(moves):
    if (not isinstance(moves, list) or not 1 <= len(moves) <= 160
            or any(not isinstance(m, str) for m in moves)):
        raise ValueError('history requires 1..160 explicit UCI moves')
    board = chess.Board()
    frames = [board.copy(stack=True)]
    for text in moves:
        if board.is_game_over(claim_draw=False):
            raise ValueError('history continues after automatic game ending')
        move = chess.Move.from_uci(text)
        if move not in board.legal_moves:
            raise ValueError('history contains an illegal move')
        board.push(move)
        frames.append(board.copy(stack=True))
    return frames


def validate(spec):
    if (not isinstance(spec, dict)
            or set(spec) != {'schema_version', 'cases', 'excluded_position_sha256'}
            or spec['schema_version'] != 2):
        raise ValueError('explicit V2 case specification required')
    excluded = spec['excluded_position_sha256']
    if (not isinstance(excluded, list)
            or any(not isinstance(h, str) or not re.fullmatch('[0-9a-f]{64}', h) for h in excluded)):
        raise ValueError('exclusion list requires SHA-256 position identities')
    if not isinstance(spec['cases'], list) or not 1 <= len(spec['cases']) <= 512:
        raise ValueError('bounded nonempty case list required')
    seen_ids, families, positions = set(), {}, {}
    checked = []
    for case in spec['cases']:
        if not isinstance(case, dict) or not BASE <= case.keys():
            raise ValueError('case fields required')
        task = case['task']
        extra = ({'frames', 'query_ply', 'query_squares', 'alternative_moves'}
                 if task == 'history' else {'proposal'} if task == 'correction' else set())
        if set(case) != BASE | extra or task not in TASKS:
            raise ValueError('unexpected task fields')
        for name in ['id', 'family']:
            if not isinstance(case[name], str) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}', case[name]):
                raise ValueError('safe case/family identity required')
        if case['id'] in seen_ids:
            raise ValueError('duplicate case identity')
        seen_ids.add(case['id'])
        if case['split'] not in SPLITS or case['style'] not in STYLES or case['orientation'] not in {'white', 'black'}:
            raise ValueError('unknown split, rendering style or orientation')
        family, split = case['family'], case['split']
        if family in families and families[family] != split:
            raise ValueError('source family crosses splits')
        families[family] = split
        boards = history(case['moves'])
        final = boards[-1]
        scored = [final]
        rendered = [(len(boards) - 1, final)]
        alternative = None
        if task == 'history':
            frames, ply, squares = case['frames'], case['query_ply'], case['query_squares']
            if (not isinstance(frames, list) or not 2 <= len(frames) <= 24
                    or any(type(n) is not int or not 0 <= n < len(boards) for n in frames)
                    or frames != sorted(set(frames)) or frames[-1] != len(boards) - 1):
                raise ValueError('ordered unique history frame plies including final required')
            if type(ply) is not int or not 0 < ply < len(boards) - 1 or ply not in frames:
                raise ValueError('queried past checkpoint must be shown, before final')
            if (not isinstance(squares, list) or not 1 <= len(squares) <= 64
                    or len(set(squares)) != len(squares)
                    or any(s not in chess.SQUARE_NAMES for s in squares)):
                raise ValueError('unique query squares required')
            alternative = history(case['alternative_moves'])
            if (len(alternative) != len(boards)
                    or alternative[-1].fen(en_passant='fen') != final.fen(en_passant='fen')):
                raise ValueError('alternative must end in identical full state at same ply')
            target = [occupancy(boards[ply])[s] for s in squares]
            other = [occupancy(alternative[ply])[s] for s in squares]
            if target == other:
                raise ValueError('alternative must change the queried past answer')
            scored.append(boards[ply])
            rendered = [(n, boards[n]) for n in frames]
        elif final.is_game_over():
            raise ValueError('move-choice task requires nonterminal position')
        if task == 'correction':
            if (not isinstance(case['proposal'], str)
                    or not re.fullmatch('[a-h][1-8][a-h][1-8][qrbn]?', case['proposal'])):
                raise ValueError('proposal requires coordinate UCI notation')
            proposal = chess.Move.from_uci(case['proposal'])
            if proposal in final.legal_moves:
                raise ValueError('injected proposal must actually be illegal')
        if any(position_hash(b) in excluded for b in [b for _, b in rendered] + scored):
            raise ValueError('case exposes an excluded prior benchmark position')
        # Every observed frame can teach a later task. Only the literal initial
        # setup frame (ply zero) is exempt; scored states never receive exemption.
        exposed = [b for ply, b in rendered if ply != 0]
        for board in scored + exposed:
            key = position_hash(board)
            if key in positions and positions[key] != (family, split):
                raise ValueError('scored or exposed position crosses families or splits')
            positions[key] = (family, split)
        checked.append((case, boards, alternative))
    return checked


def render(board, orientation, style):
    """Deterministic vector stimulus; UI clutter never covers board squares."""
    import pymupdf
    facing = orientation == 'white'
    colors = ({'square light': '#b1c1ba', 'square dark': '#556c63'}
              if style in {'angled', 'clutter'} else None)
    inner = chess.svg.board(board, orientation=facing, coordinates=True,
                            size=480, colors=colors or {}, arrows=[],
                            lastmove=None, check=None)
    # MuPDF ignores nested SVG x/y offsets. Use ordinary translated groups so
    # the rendered board remains inset, including after rotation.
    content = inner.split('>', 1)[1].rsplit('</svg>', 1)[0]
    viewbox = [float(x) for x in re.search(r'viewBox="([^"]+)"', inner).group(1).split()]
    if viewbox[:2] != [0, 0] or viewbox[2] != viewbox[3] or viewbox[2] <= 0:
        raise ValueError('unexpected chess SVG coordinate system')
    board_scale = 480 / viewbox[2]
    angle = -7 if style == 'angled' else 0
    panels = ''
    if style == 'clutter':
        panels = ''.join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="#293c36"/>'
                         for x, y, w, h in [(20, 140, 102, 210), (638, 210, 100, 280), (28, 555, 95, 95)])
        panels += '<text x="32" y="170" fill="#c7d5ce" font-size="14">Game panel</text>'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="760" height="760" viewBox="0 0 760 760">'
           '<rect width="760" height="760" fill="#17221e"/>'
           '<text x="40" y="65" fill="#eee9dc" font-size="25" font-family="sans-serif">Study position</text>'
           f'{panels}<g transform="rotate({angle} 380 380)"><g transform="translate(140 140) scale({board_scale})">'
           f'{content}</g></g><text x="40" y="710" fill="#afc0b5" font-size="16" font-family="sans-serif">'
           f'{escape("White" if facing else "Black")} at bottom</text></svg>').encode()
    pixels = 512 if style == 'compact' else 760
    with pymupdf.open(stream=svg, filetype='svg') as doc:
        png = doc[0].get_pixmap(matrix=pymupdf.Matrix(pixels / 760, pixels / 760), alpha=False).tobytes('png')
    return png, digest(svg)


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def build(spec, output):
    checked = validate(spec)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    players, truths = [], []
    try:
        write_new(output / 'evaluator/source-spec.json', spec)
        for case, boards, alternative in checked:
            def image_at(ply):
                png, svg_sha = render(boards[ply], case['orientation'], case['style'])
                relative = f'images/{digest(png)}.png'
                path = output / relative
                path.parent.mkdir(exist_ok=True)
                if not path.exists():
                    with path.open('xb') as stream:
                        stream.write(png)
                elif path.read_bytes() != png:
                    raise ValueError('image commitment collision')
                return {'path': relative, 'sha256': digest(png), 'svg_sha256': svg_sha}
            final = boards[-1]
            rules = {'side_to_move': 'white' if final.turn else 'black',
                     'castling': final.castling_xfen(),
                     'legal_en_passant_square': chess.square_name(final.ep_square) if final.has_legal_en_passant() else None}
            player = {'id': case['id'], 'task': case['task'], 'orientation': case['orientation'],
                      'image': image_at(len(boards) - 1), 'rules': rules}
            truth = {'id': case['id'], 'family': case['family'], 'split': case['split'],
                     'task': case['task'], 'fen': final.fen(en_passant='fen'),
                     'position_sha256': position_hash(final), 'piece_map': occupancy(final),
                     'history_uci': case['moves'], 'render_style': case['style']}
            if case['task'] == 'history':
                player['history_frames'] = [{'ply': n, 'image': image_at(n)} for n in case['frames']]
                player['question'] = {'checkpoint_ply': case['query_ply'], 'squares': case['query_squares']}
                past = occupancy(boards[case['query_ply']])
                truth['history_answer'] = {s: past[s] for s in case['query_squares']}
                truth['nonuniqueness_witness_uci'] = case['alternative_moves']
                truth['history_record'] = [{'ply': n, 'piece_map': occupancy(boards[n])} for n in case['frames']]
            elif case['task'] == 'correction':
                player['initial_proposal'] = case['proposal']
                truth['feedback_treatment'] = 'The proposed move is illegal.'
            write_new(output / f'player/{case["id"]}.json', player)
            players.append({'id': case['id'], 'path': f'player/{case["id"]}.json'})
            truths.append(truth)
        write_new(output / 'evaluator/cases.json', {'cases': truths})
        files = {str(p.relative_to(output)): digest(p.read_bytes())
                 for p in sorted(output.rglob('*')) if p.is_file()}
        manifest = {'schema_version': 2, 'status': 'sealed', 'cases': players,
                    'source_sha256': digest(Path(__file__).read_bytes()),
                    'spec_sha256': digest(json.dumps(spec, sort_keys=True, allow_nan=False).encode()),
                    'renderer': {'chess': chess.__version__, 'hints': False,
                                 'styles': sorted(STYLES), 'clutter_occludes_squares': False},
                    'files': files, 'notes': ['Truth and history records are evaluator-owned.',
                        'Common rules metadata is explicit diagnostic assistance, not a screenshot-only browser game.',
                        'No engine query or model execution performed.']}
        write_new(output / 'manifest.json', manifest)
        return manifest
    except BaseException as exc:
        write_new(output / 'generation-failure.json', {'error_type': type(exc).__name__,
                  'note': 'Preserve partial output; no overwrite or automatic retry.'})
        raise


def verify(output):
    output = Path(output).resolve(strict=True)
    manifest = json.loads((output / 'manifest.json').read_text())
    if manifest.get('status') != 'sealed' or manifest.get('schema_version') != 2:
        raise ValueError('sealed V2 manifest required')
    expected_files = manifest['files']
    actual_files = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}
    if actual_files != set(expected_files) | {'manifest.json'}:
        raise ValueError('corpus file inventory changed')
    for relative, expected in manifest['files'].items():
        if Path(relative).is_absolute():
            raise ValueError('relative corpus paths required')
        path = (output / relative).resolve(strict=True)
        if not path.is_relative_to(output) or digest(path.read_bytes()) != expected:
            raise ValueError('corpus file changed or escapes root')
    spec = json.loads((output / 'evaluator/source-spec.json').read_text())
    checked = validate(spec)
    if digest(json.dumps(spec, sort_keys=True, allow_nan=False).encode()) != manifest['spec_sha256']:
        raise ValueError('source specification commitment changed')
    if {c['id'] for c, _, _ in checked} != {p['id'] for p in manifest['cases']}:
        raise ValueError('manifest case inventory differs from specification')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        result = verify(args.output)
    else:
        if args.spec is None:
            parser.error('--spec required for creation')
        result = build(json.loads(args.spec.read_text()), args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

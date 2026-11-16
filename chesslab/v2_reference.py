"""Bounded evaluator-owned snapshot analysis with proven engine termination.

Never expose requests, scores or this module to an unaided player. Operators must
verify subject completion before reference evaluation; search assistance instead
requires its own prospectively declared input/budget contract.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import chess
import chess.engine

from . import engine_work
from . import evaluate as evaluator


OPTIONS = {'Threads': 1, 'Hash': 16, 'UCI_LimitStrength': False,
           'Skill Level': 20, 'SyzygyPath': ''}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def request(value):
    if (not isinstance(value, dict) or set(value) != {'engine', 'fen', 'nodes', 'timeout_seconds', 'selected_move'}
            or type(value['nodes']) is not int or not 1 <= value['nodes'] <= 10_000_000
            or type(value['timeout_seconds']) is not int or not 1 <= value['timeout_seconds'] <= 30):
        raise ValueError('explicit bounded snapshot reference request required')
    board = chess.Board(value['fen'])
    if not board.is_valid() or board.is_game_over(claim_draw=False):
        raise ValueError('valid nonterminal standard position required')
    path = Path(value['engine']).resolve(strict=True)
    if not path.is_file():
        raise ValueError('engine file required')
    selected = value['selected_move']
    if selected is not None:
        if not isinstance(selected, str) or chess.Move.from_uci(selected) not in board.legal_moves:
            raise ValueError('selected analysis requires a legal UCI move')
    return board, path


async def _operate(board, path, nodes, timeout, selected):
    transport = protocol = None
    commands = []

    async def bounded(coroutine):
        # Cancelling analyse() directly cancels python-chess's completion future;
        # its later process-exit callback can then fail before publishing exit.
        # Keep each command alive until transport cleanup and collect its result.
        task = asyncio.create_task(coroutine)
        commands.append(task)
        return await asyncio.wait_for(asyncio.shield(task), timeout)

    report = {'status': 'failed', 'process_stopped': False, 'process_returncode': None,
              'analyses': [], 'options': dict(OPTIONS), 'hash_reset_each_search': True,
              'root_policy': 'full-FEN snapshot; no earlier repetition history'}
    try:
        # Obtain the raw handle before the UCI handshake so initialization failures
        # can still prove subprocess exit. A spawn failure without a handle cannot.
        transport, protocol = await asyncio.wait_for(chess.engine.UciProtocol.popen(str(path)), timeout)
        await bounded(protocol.initialize())
        report['engine_id'] = dict(protocol.id)
        report['option_defaults'] = {name: option.default for name, option in protocol.options.items()}
        if ('Stockfish' not in protocol.id.get('name', '')
                or not (set(OPTIONS) | {'Clear Hash'}) <= protocol.options.keys()):
            raise ValueError('Stockfish with required explicit options expected')
        await bounded(protocol.configure(OPTIONS))
        for chosen in [None] + ([selected] if selected is not None else []):
            await bounded(protocol.configure({'Clear Hash': None}))
            began = time.monotonic_ns()
            info = await bounded(protocol.analyse(board, chess.engine.Limit(nodes=nodes),
                game=object(), root_moves=[chess.Move.from_uci(chosen)] if chosen else None,
                info=chess.engine.INFO_ALL))
            score = evaluator.score_record(info, board.turn)
            score.update({'search_active_ns': time.monotonic_ns() - began,
                          'root_move': chosen, 'requested_nodes': nodes})
            report['analyses'].append(score)
            if (chess.Move.from_uci(score['pv'][0]) not in board.legal_moves
                    or chosen is not None and score['pv'][0] != chosen):
                raise ValueError('reference principal variation violates root request')
        report['status'] = 'analyzed'
    except Exception as exc:
        report['error_type'] = type(exc).__name__
    finally:
        if transport is not None:
            try:
                await bounded(protocol.quit())
            except Exception as exc:
                report['quit_error_type'] = type(exc).__name__
            finally:
                transport.close()
            try:
                code = await asyncio.wait_for(asyncio.shield(protocol.returncode), 2)
                if type(code) is not int:
                    raise ValueError('actual process returncode unavailable')
                report.update(process_stopped=True, process_returncode=code)
            except Exception as exc:
                report.update(status='exit_unconfirmed', exit_error_type=type(exc).__name__)
            if commands:
                # The process is closed; collect both successful and failed
                # command tasks without unhandled-future warnings. Do not block
                # indefinitely if a library task itself fails to terminate.
                collected = asyncio.gather(*commands, return_exceptions=True)
                try:
                    await asyncio.wait_for(asyncio.shield(collected), 1)
                except asyncio.TimeoutError:
                    report['command_drain_timeout'] = True
                    collected.cancel()
                    await asyncio.gather(collected, return_exceptions=True)
        if not report['process_stopped']:
            report['status'] = 'exit_unconfirmed'
    return report


def analyze(request_path, output, *, budget, identity):
    """One immutable operation; no selective deepening or automatic retries."""
    request_path = Path(request_path).resolve(strict=True)
    raw = request_path.read_bytes()
    value = json.loads(raw)
    board, path = request(value)
    binary_sha = _sha(path)
    source = {str(p): _sha(p) for p in
              [Path(__file__), Path(engine_work.__file__), Path(evaluator.__file__)]}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    searches = 1 + (value['selected_move'] is not None)
    # Spawn + init + configure + two commands/search + quit + exit wait, with
    # another second for Python overhead. Each blocking operation is bounded.
    allowance = (4 + 2 * searches) * value['timeout_seconds'] + 3
    reservation = engine_work.reserve(budget, identity, allowance,
        metadata={'purpose': 'snapshot search/reference', 'request_sha256': hashlib.sha256(raw).hexdigest(),
                  'output': str(output.resolve()), 'source_sha256': source})
    _write(output / 'inputs.json', {'request': value, 'request_path': str(request_path),
        'request_sha256': hashlib.sha256(raw).hexdigest(), 'engine_sha256': binary_sha,
        'source_sha256': source, 'reservation': reservation, 'chess_version': chess.__version__,
        'at': datetime.now(timezone.utc).isoformat()})
    started = time.monotonic_ns()
    result = asyncio.run(_operate(board, path, value['nodes'], value['timeout_seconds'], value['selected_move']))
    result['active_ns'] = time.monotonic_ns() - started
    result['engine_binary_unchanged'] = _sha(path) == binary_sha
    result['request_unchanged'] = request_path.read_bytes() == raw
    result['sources_unchanged'] = all(_sha(p) == h for p, h in source.items())
    result['fen'] = board.fen()
    result['nodes_per_search'] = value['nodes']
    result['selected_move'] = value['selected_move']
    if len(result['analyses']) == searches and result['status'] == 'analyzed':
        best = result['analyses'][0]
        result['best_move'] = best['pv'][0]
        if value['selected_move'] is not None:
            chosen = result['analyses'][1]
            comparable = (all(s['cp'] is not None and s['mate'] is None
                and not s['lowerbound'] and not s['upperbound'] for s in [best, chosen]))
            delta = best['cp'] - chosen['cp'] if comparable else None
            result.update(best_move_agreement=best['pv'][0] == value['selected_move'],
                cp_comparable=comparable, cp_loss_raw=delta,
                finite_search_inversion=delta < 0 if delta is not None else None)
    receipt = output / 'result.json'
    _write(receipt, result)
    if not result['process_stopped']:
        raise RuntimeError('engine exit unconfirmed; full allowance retained, inspect process before proceeding')
    engine_work.settle(budget, identity, result['active_ns'], receipt=receipt)
    if result['status'] != 'analyzed' or not all(result[k] for k in
            ['engine_binary_unchanged', 'request_unchanged', 'sources_unchanged']):
        raise RuntimeError('reference operation failed; immutable failure retained, no automatic retry')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--budget', required=True, type=Path)
    parser.add_argument('--identity', required=True)
    args = parser.parse_args()
    result = analyze(args.request, args.output, budget=args.budget, identity=args.identity)
    print(json.dumps({k: result[k] for k in ['status', 'process_stopped', 'active_ns']}, indent=2))


if __name__ == '__main__':
    main()

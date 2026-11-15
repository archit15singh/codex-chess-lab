"""Synthetic PGNs and evidence fixtures; these are not research observations."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import chess
    import chess.engine
    from chesslab.evaluate import analyse_game, audit_actions, evaluate, parse_game, score_record
except ModuleNotFoundError as exc:
    if exc.name != 'chess':
        raise
    chess = None

MATE = '[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n'
OPEN = '[Result "*"]\n\n1. e4 e5 *\n'


@unittest.skipIf(chess is None, 'post-game dependency not installed in this interpreter')
class PgnTests(unittest.TestCase):
    def test_mate_and_annotation_comments(self):
        game = parse_game('[Event "Synthetic"]\n' + MATE.replace('f3', 'f3?! {fixture} $2'))
        self.assertEqual(len(game.moves), 4)
        self.assertTrue(game.final.is_checkmate())
        self.assertEqual(game.final.result(), '0-1')

    def test_malformed_illegal_and_multiple_games(self):
        bad = [
            '[Result "*"]\n1. e5 *',
            '[Result "*"]\n1. e4 arbitrary-garbage *',
            '[Result "*"]\n1. e4# *',
            '[Result "*"]\n1. e4+ *',
            OPEN + MATE,
            OPEN.replace('*\n', '* trailing'),
            '[Result "*"]\n1. e4 {unclosed *',
            OPEN.replace('1. e4', '2. e4'),
            '[Result "*"]\n1. -- *',
            '[Result "*"]\n1. e4 (1. d4) *',
            '[Result "*"]\n1. e4',
            '[Result "*"]\n[Result "*"]\n*',
            '[Result "*"]\n[Variant "Atomic"]\n*',
        ]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_game(text)

    def test_header_result_and_board_terminal_agreement(self):
        with self.assertRaisesRegex(ValueError, 'movetext'):
            parse_game(MATE.replace('[Result "0-1"]', '[Result "1-0"]'))
        with self.assertRaisesRegex(ValueError, 'board-terminal'):
            parse_game(MATE.replace('0-1', '1-0'))
        with self.assertRaises(ValueError):
            parse_game(MATE.replace('Qh4#', 'Qh4# 3. a3'))
        with self.assertRaisesRegex(ValueError, 'max_plies'):
            parse_game(MATE, max_plies=3)

    def test_fen_start_and_invalid_fen(self):
        text = '[SetUp "1"]\n[FEN "7k/6Q1/5K2/8/8/8/8/8 b - - 0 1"]\n[Result "1-0"]\n\n1-0'
        self.assertTrue(parse_game(text).final.is_checkmate())
        with self.assertRaisesRegex(ValueError, 'SetUp'):
            parse_game(text.replace('[SetUp "1"]\n', ''))
        with self.assertRaisesRegex(ValueError, 'invalid starting'):
            parse_game(text.replace('7k/6Q1/5K2', '8/6Q1/5K2'))

    def test_nonterminal_result_requires_external_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            pgn = Path(tmp) / 'synthetic.pgn'
            pgn.write_text('[Result "1-0"]\n1. e4 e5 1-0')
            result = evaluate(pgn)
            self.assertFalse(result['board_terminal'])
            self.assertIsNone(result['board_result'])
            self.assertIsNone(result['rating'])
            with self.assertRaisesRegex(ValueError, 'not terminal'):
                evaluate(pgn, require_board_terminal=True)

    def test_cli_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'synthetic.pgn', Path(tmp) / 'result.json'
            source.write_text(MATE)
            target.write_text('prior evidence')
            process = subprocess.run([sys.executable, '-m', 'chesslab.evaluate', str(source),
                                      '--output', str(target)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(target.read_text(), 'prior evidence')


@unittest.skipIf(chess is None, 'post-game dependency not installed in this interpreter')
class EvidenceTests(unittest.TestCase):
    def test_screenshot_bytes_and_escape_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'evidence'
            root.mkdir()
            shot = root / 'board.png'
            shot.write_bytes(b'synthetic-image-bytes')
            log = root / 'actions.jsonl'
            ref = {'file': 'board.png', 'sha256': hashlib.sha256(shot.read_bytes()).hexdigest()}
            log.write_text(json.dumps({'pre': ref}) + '\n')
            result = audit_actions(log)
            self.assertEqual(result['references_verified'], 1)
            self.assertFalse(result['visual_consistency_verified'])
            shot.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                audit_actions(log)
            outside = Path(tmp) / 'outside.png'
            outside.write_bytes(b'outside')
            for name in ('../outside.png', str(outside)):
                ref = {'file': name, 'sha256': hashlib.sha256(outside.read_bytes()).hexdigest()}
                log.write_text(json.dumps({'pre': ref}))
                with self.subTest(name=name), self.assertRaises(ValueError):
                    audit_actions(log)
            (root / 'link.png').symlink_to(outside)
            ref['file'] = 'link.png'
            log.write_text(json.dumps({'pre': ref}))
            with self.assertRaisesRegex(ValueError, 'escapes'):
                audit_actions(log)

    def test_empty_references_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'actions.jsonl'
            log.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'no screenshot'):
                audit_actions(log)


@unittest.skipIf(chess is None, 'post-game dependency not installed in this interpreter')
class EngineTests(unittest.TestCase):
    def test_mate_score_is_not_centipawns(self):
        record = score_record({'score': chess.engine.PovScore(chess.engine.Mate(2), chess.BLACK),
                               'pv': [chess.Move.from_uci('e2e4')]}, chess.WHITE)
        self.assertIsNone(record['cp'])
        self.assertEqual(record['mate'], -2)

    def test_same_root_side_limits_and_clear_hash(self):
        class Transport:
            closed = False
            def close(self):
                self.closed = True
        class Engine:
            id = {'name': 'Stockfish synthetic mock'}
            options = {x: chess.engine.Option(x, 'spin', 1, None, None, None)
                       for x in ('Threads', 'Hash', 'Clear Hash')}
            def __init__(self, bound=None):
                self.bound = bound
                self.calls, self.configs = [], []
                self.quit_called = False
            async def configure(self, value):
                self.configs.append(value)
            async def analyse(self, board, limit, **kwargs):
                self.calls.append((board.fen(), limit.nodes, kwargs.get('root_moves')))
                move = kwargs.get('root_moves', None)
                info = {'score': chess.engine.PovScore(chess.engine.Cp(20), board.turn),
                        'pv': move or [next(iter(board.legal_moves))], 'nodes': limit.nodes}
                if self.bound:
                    info[self.bound] = True
                return info
            async def quit(self):
                self.quit_called = True
        engine, transport = Engine(), Transport()
        async def startup(*args):
            return transport, engine
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'synthetic-engine'
            binary.write_bytes(b'not executable: mocked')
            with patch('chess.engine.popen_uci', startup):
                result = asyncio.run(analyse_game(parse_game(OPEN), binary, nodes=5,
                                                  hash_mb=16, timeout=1, total_timeout=5))
            original_engine, original_transport = engine, transport
            for bound in ('lowerbound', 'upperbound'):
                engine, transport = Engine(bound), Transport()
                with self.subTest(bound=bound), patch('chess.engine.popen_uci', startup):
                    bounded = asyncio.run(analyse_game(parse_game(OPEN), binary, nodes=5,
                                                       hash_mb=16, timeout=1, total_timeout=5))
                    for row in bounded['rows']:
                        self.assertTrue(row['best'][bound])
                        self.assertIsNone(row['cp_loss_raw'])
                        self.assertIsNone(row['cp_loss_nonnegative'])
                        self.assertIsNone(row['bounded_search_inversion'])
            engine, transport = original_engine, original_transport
        self.assertEqual(result['option_defaults'], {'Threads': 1, 'Hash': 1, 'Clear Hash': 1})
        self.assertEqual(result['options'], {'Threads': 1, 'Hash': 16})
        self.assertEqual(len(engine.calls), 4)
        for before, selected in zip(engine.calls[::2], engine.calls[1::2]):
            self.assertEqual(before[:2], selected[:2])
            self.assertIsNone(before[2])
            self.assertEqual(len(selected[2]), 1)
        self.assertEqual(engine.configs.count({'Clear Hash': None}), 4)
        self.assertTrue(transport.closed and engine.quit_called)
        self.assertEqual(result['rows'][1]['turn'], 'black')
        self.assertEqual(result['rows'][0]['cp_loss_raw'], 0)

    def test_per_search_watchdog_closes_engine(self):
        class Transport:
            closed = False
            def close(self):
                self.closed = True
        class Engine:
            id = {'name': 'Stockfish synthetic hanging mock'}
            options = {x: chess.engine.Option(x, 'spin', 1, None, None, None)
                       for x in ('Threads', 'Hash', 'Clear Hash')}
            async def configure(self, value):
                pass
            async def analyse(self, *args, **kwargs):
                await asyncio.sleep(10)
            async def quit(self):
                pass
        transport = Transport()
        async def startup(*args):
            return transport, Engine()
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'synthetic-engine'
            binary.write_bytes(b'mocked')
            with patch('chess.engine.popen_uci', startup), self.assertRaises(asyncio.TimeoutError):
                asyncio.run(analyse_game(parse_game(OPEN), binary, nodes=5,
                                         hash_mb=16, timeout=.01, total_timeout=1))
        self.assertTrue(transport.closed)


if __name__ == '__main__':
    unittest.main()

"""Synthetic construction checks; these are not experimental chess results."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

try:
    import chess
    from chesslab import corpus
except ImportError:
    chess = corpus = None


class FakeEngine:
    metadata = {'engine_id': {'name': 'Synthetic fixture; no chess strength'}}
    elapsed = 0.0

    async def query(self, board):
        return {'candidates': sorted(m.uci() for m in board.legal_moves)[:3],
                'rows': [], 'elapsed_seconds': 0.0}


@unittest.skipIf(chess is None, 'isolated evaluator dependencies required')
class CorpusTests(unittest.TestCase):
    def test_frozen_map_and_orientation_balance(self):
        counts = {}
        for family in corpus.FAMILIES:
            counts[family.split] = counts.get(family.split, 0) + len(corpus.checkpoints(family))
            pairs = [(ply % 2 == 0, corpus.orientation(family, ply))
                     for ply in corpus.checkpoints(family)]
            self.assertEqual(sum(turn for turn, _ in pairs), len(pairs) // 2)
            self.assertEqual(sum(facing for _, facing in pairs), len(pairs) // 2)
            if family.split == 'final':
                self.assertEqual(len(set(pairs)), 4)
        self.assertEqual(counts, {'training': 6, 'development': 6, 'final': 24})
        corpus.validate_families(corpus.FAMILIES)

    def test_seeded_legal_generation_is_deterministic(self):
        family = corpus.Family('fixture', 'training', ('a2a3',))
        traces = [[], []]
        runs = [asyncio.run(corpus.candidate(family, 145, FakeEngine(), trace.append))
                for trace in traces]
        self.assertEqual(traces[0], traces[1])
        self.assertEqual([b.fen() for b in runs[0]], [b.fen() for b in runs[1]])
        self.assertEqual(len(runs[0]), 41)
        board = chess.Board()
        for move in runs[0][-1].move_stack:
            self.assertIn(move, board.legal_moves)
            board.push(move)
        self.assertTrue(any(row.get('query') is not None for row in traces[0]))
        self.assertTrue(any(row.get('policy') == 'uniform-legal' for row in traces[0]))
        self.assertNotEqual(corpus.candidate_seed(1, 'fixture', 1),
                            corpus.candidate_seed(1, 'fixture', 2))

    def test_only_checkpoints_are_deduplicated_across_families_and_splits(self):
        family = corpus.Family('fixture', 'training', ())
        frames = asyncio.run(corpus.candidate(family, 145, FakeEngine(), lambda _: None))
        initial = corpus.canonical(frames[0])
        self.assertIsNone(corpus.rejection(frames, family, {initial}))
        self.assertEqual(corpus.rejection(frames, family, {corpus.canonical(frames[15])}),
                         'duplicate-across-family-checkpoint')
        # A split change never bypasses the global checkpoint set.
        final = corpus.Family('fixture-final', 'final', ())
        self.assertEqual(corpus.rejection(frames, final, {corpus.canonical(frames[15])}),
                         'duplicate-across-family-checkpoint')
        altered = frames.copy()
        altered[40] = altered[15]
        self.assertEqual(corpus.rejection(altered, family, set()),
                         'duplicate-within-family-checkpoint')
        self.assertEqual(corpus.rejection(frames[:30], family, set()), 'terminal-or-short-game')

    def test_canonical_legal_ep_and_counters(self):
        board = chess.Board()
        board.push_uci('e2e4')
        self.assertEqual(corpus.canonical(board).split()[-1], '-')
        changed = board.copy()
        changed.halfmove_clock = 90
        changed.fullmove_number = 80
        self.assertEqual(corpus.canonical(board), corpus.canonical(changed))
        changed.castling_rights = 0
        self.assertNotEqual(corpus.canonical(board), corpus.canonical(changed))

    def test_player_allowlist_has_common_rules_but_no_oracle_occupancy(self):
        board = chess.Board()
        item = corpus.player_item('p001', board, {'path': 'images/x.png', 'sha256': 'x'}, True)
        self.assertEqual(set(item), {'schema_version', 'item_id', 'image', 'orientation', 'rules'})
        self.assertEqual(set(item['rules']), {'side_to_move', 'castling',
                                             'en_passant_square', 'halfmove_clock'})
        encoded = json.dumps(item)
        for forbidden in ('fen', 'occupancy', 'history', 'legal_moves', 'best_move', 'family', 'split'):
            self.assertNotIn(forbidden, encoded)
        self.assertNotIn(board.board_fen(), encoded)

    def test_exclusive_build_manifest_and_failed_retry_evidence(self):
        family = corpus.Family('fixture', 'development', ())
        frames = asyncio.run(corpus.candidate(family, 145, FakeEngine(), lambda _: None))
        async def synthetic(*args):
            return frames
        def renderer(board, facing):
            raw = (corpus.canonical(board) + str(facing)).encode()
            return b'fixture-not-a-real-image:' + raw, corpus.digest(raw)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'corpus'
            with patch.object(corpus, 'candidate', synthetic):
                manifest = asyncio.run(corpus.build(output, FakeEngine(), source_commit='fixture',
                    design_sha256='fixture', families=(family,), renderer=renderer))
            self.assertEqual(manifest['counts']['items'], 2)
            for relative, expected in manifest['files'].items():
                self.assertEqual(corpus.digest((output / relative).read_bytes()), expected)
            evaluator = json.loads((output / 'evaluator/items.json').read_text())
            self.assertEqual(evaluator['items'][0]['fen'], frames[15].fen())
            self.assertEqual(len(json.loads((output / 'evaluator/families.json').read_text())
                                 ['families'][0]['frames']), 41)
            with self.assertRaises(FileExistsError):
                asyncio.run(corpus.build(output, FakeEngine(), source_commit='fixture',
                    design_sha256='fixture', families=(family,), renderer=renderer))
            failing = Path(temp) / 'failing'
            duplicate = corpus.Family('same-position', 'final', ())
            with patch.object(corpus, 'candidate', synthetic):
                with self.assertRaisesRegex(ValueError, 'candidate limit exhausted'):
                    asyncio.run(corpus.build(failing, FakeEngine(), source_commit='fixture',
                        design_sha256='fixture', families=(family, duplicate), renderer=renderer))
            records = [json.loads(line) for line in (failing / 'construction.jsonl').read_text().splitlines()]
            rejected = [row for row in records if row['kind'] == 'rejected']
            self.assertEqual(len(rejected), 10)
            self.assertEqual(len({r['seed'] for r in rejected}), 10)
            self.assertEqual(records[-1]['kind'], 'failed')
            self.assertFalse((failing / 'manifest.json').exists())

    def test_starting_board_renderer_smoke(self):
        import pymupdf
        png, svg_hash = corpus.render(chess.Board(), chess.WHITE)
        self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(len(svg_hash), 64)
        pixmap = pymupdf.Pixmap(png)
        self.assertEqual((pixmap.width, pixmap.height), (585, 585))
        self.assertEqual(corpus.render(chess.Board(), chess.WHITE), (png, svg_hash))
        self.assertNotEqual(corpus.render(chess.Board(), chess.BLACK)[1], svg_hash)

    def test_engine_query_resets_hash_bounds_nodes_and_records_observed_work(self):
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / 'fake-stockfish'
            binary.write_bytes(b'not executable; protocol is mocked')
            engine = corpus.GeneratorEngine(binary)
            board = chess.Board()
            calls = []
            async def configure(options):
                calls.append(('configure', options))
            async def analyse(position, limit, **kwargs):
                calls.append(('analyse', limit.nodes, kwargs['multipv']))
                self.assertEqual(position.fen(), board.fen())
                return [{'pv': [chess.Move.from_uci('e2e4')], 'nodes': 1007,
                         'depth': 4, 'time': 0.001}]
            class Protocol:
                pass
            engine.protocol = Protocol()
            engine.protocol.configure = configure
            engine.protocol.analyse = analyse
            result = asyncio.run(engine.query(board))
            self.assertEqual(calls, [('configure', {'Clear Hash': None}), ('analyse', 1000, 3)])
            self.assertEqual(result['rows'][0]['nodes'], 1007)
            self.assertEqual(result['candidates'], ['e2e4'])
            self.assertGreaterEqual(engine.elapsed, 0)
            engine.elapsed = engine.total_seconds
            with self.assertRaisesRegex(TimeoutError, 'budget exhausted'):
                asyncio.run(engine.query(board))
            self.assertEqual(len(calls), 2)

    def test_query_failure_is_preserved_without_candidate_replacement(self):
        engine = FakeEngine()
        engine.query = AsyncMock(side_effect=TimeoutError('fixture timeout'))
        records = []
        family = corpus.Family('fixture', 'training', ())
        with self.assertRaises(TimeoutError):
            asyncio.run(corpus.candidate(family, 145, engine, records.append))
        self.assertEqual(records[-2]['kind'], 'query-started')
        self.assertEqual(records[-1]['kind'], 'query-failed')
        self.assertEqual(engine.query.await_count, 1)


if __name__ == '__main__':
    unittest.main()

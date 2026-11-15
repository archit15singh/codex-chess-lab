"""Synthetic scorer regressions; no actual study items, actors or engines."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import chess
    from chesslab import position_score as scoring, position_trial, corpus
except ImportError:
    chess = None


@unittest.skipIf(chess is None, 'isolated evaluator dependencies required')
class PositionScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.completion = self.root / 'fixture-completed.json'
        self.completion.write_text('{"status":"completed","actor_id":"synthetic-fixture"}')
        self.engine = self.root / 'not-a-real-engine'
        self.engine.write_bytes(b'synthetic mock only; never executed')
        self.zero = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.make_fixture([])

    def tearDown(self):
        self.temp.cleanup()

    def make_fixture(self, moves, arm='A'):
        self.corpus = self.root / f'corpus-{len(list(self.root.glob("corpus-*")))}'
        (self.corpus / 'player').mkdir(parents=True)
        (self.corpus / 'evaluator').mkdir()
        (self.corpus / 'images').mkdir()
        self.board = chess.Board()
        for move in moves:
            self.board.push_uci(move)
        image_path = self.corpus / 'images/fixture.png'
        image_path.write_bytes(b'synthetic pixels placeholder; no experimental image')
        player = corpus.player_item('pfixture', self.board,
            {'path': 'images/fixture.png', 'sha256': position_trial.sha(image_path)}, chess.WHITE)
        player_path = self.corpus / 'player/pfixture.json'
        player_path.write_text(json.dumps(player))
        item = {'item_id': 'pfixture', 'family_id': 'synthetic-fixture', 'split': 'training',
                'ply': len(moves), 'history_uci': moves, 'player_path': 'player/pfixture.json',
                'fen': self.board.fen(), 'canonical_fen': corpus.canonical(self.board),
                'occupancy': {chess.square_name(s): p.symbol() for s, p in self.board.piece_map().items()}}
        item_path = self.corpus / 'evaluator/items.json'
        item_path.write_text(json.dumps({'schema_version': 1, 'items': [item]}))
        manifest = {'status': 'sealed', 'engine_work_seconds': 100,
                    'engine': {'binary_sha256': position_trial.sha(self.engine)},
                    'files': {str(p.relative_to(self.corpus)): position_trial.sha(p)
                              for p in (player_path, image_path, item_path)}}
        (self.corpus / 'manifest.json').write_text(json.dumps(manifest))
        self.trial = self.root / ('trial-' + self.corpus.name)
        with patch('chesslab.position_trial.now', return_value=self.zero):
            position_trial.prepare(self.corpus, 'pfixture', arm, self.trial)
        with patch('chesslab.position_trial.now', return_value=self.zero + timedelta(seconds=1)):
            position_trial.launch(self.trial)
        self.output = self.root / ('score-' + self.corpus.name)

    def response(self, move='e2e4'):
        rules = corpus.common_rules(self.board)
        return {'move': move, 'piece_map': {s: self.board.piece_at(chess.parse_square(s)).symbol()
                 if self.board.piece_at(chess.parse_square(s)) else '.' for s in position_trial.SQUARES},
                'side_to_move': rules['side_to_move'], 'confidence': .8,
                'castling': rules['castling'], 'en_passant_square': rules['en_passant_square']}

    def submit(self, stage, value=None, seconds=10):
        path = self.root / f'{self.corpus.name}-{stage}-raw'
        path.write_bytes(value if isinstance(value, bytes) else json.dumps(value or self.response()).encode())
        with patch('chesslab.position_trial.now', return_value=self.zero + timedelta(seconds=seconds)):
            position_trial.submit(self.trial, stage, path)

    def score(self, **kwargs):
        return scoring.score_trial(self.trial, self.output, actor_completed=True,
            completion_evidence=self.completion, engine=self.engine, **kwargs)

    def evaluation(self, pgn, **kwargs):
        self.assertEqual(kwargs, {'engine': self.engine.resolve(), 'nodes': 100000,
                                 'hash_mb': 16, 'timeout': 3, 'total_timeout': 10})
        self.assertTrue((self.output / 'inputs.json').exists())
        self.assertTrue((self.output / 'measurements.json').exists())
        budget = json.loads(self.corpus.with_name(self.corpus.name + '-engine-budget.json').read_text())
        self.assertEqual(budget['operations'][-1]['status'], 'reserved')
        self.assertEqual(budget['charged_seconds'], 113)
        parsed = scoring.evaluator.parse_game(pgn.read_text())
        self.assertEqual(parsed.initial.fen(), self.board.fen())
        self.assertEqual(len(parsed.initial.move_stack), 0)
        self.assertEqual(len(parsed.moves), 1)
        self.last_parsed = parsed
        score = lambda cp: {'cp': cp, 'mate': None, 'lowerbound': False, 'upperbound': False,
                            'pv': [parsed.moves[0].uci()], 'nodes': 100009}
        row = {'fen': self.board.fen(), 'turn': 'white' if self.board.turn else 'black',
               'move': parsed.moves[0].uci(), 'best': score(100), 'selected': score(0), 'cp_loss_raw': 100}
        return {'plies': 1, 'engine_analysis': {'binary_sha256': position_trial.sha(self.engine),
                'nodes_per_search': 100000, 'searches_per_ply': 2, 'options': {'Threads': 1, 'Hash': 16},
                'hash_reset_each_search': True, 'rows': [row]}}

    def test_operator_gate_and_exclusive_output_prevent_reference_work(self):
        with patch('chesslab.position_score.evaluator.evaluate', side_effect=self.evaluation) as engine:
            with self.assertRaisesRegex(ValueError, 'completion first'):
                scoring.score_trial(self.trial, self.output, actor_completed=False,
                    completion_evidence=self.completion, engine=self.engine)
            self.assertFalse(self.output.exists())
            self.submit('initial'); self.submit('final', seconds=20)
            result = self.score()
            self.assertTrue(result['deadline_success'])
            with self.assertRaises(FileExistsError):
                self.score()
            self.assertEqual(engine.call_count, 1)

    def test_exact_transcription_rules_latency_and_fixed_reference_policy(self):
        self.submit('initial'); self.submit('final', seconds=20)
        with patch('chesslab.position_score.evaluator.evaluate', side_effect=self.evaluation):
            result = self.score()
        self.assertEqual(result['attempted_trials'], 1)
        self.assertEqual(result['initial']['latency_seconds'], 9)
        self.assertEqual(result['final']['latency_seconds'], 19)
        self.assertEqual(result['timing']['revision_seconds'], 10)
        self.assertTrue(result['final']['transcription']['exact_board'])
        self.assertTrue(result['final']['requested_rules']['exact_requested_rules'])
        self.assertEqual(result['quality']['cp_loss_raw'], 100)
        self.assertEqual(result['quality']['thresholds'], {'100': True, '200': False, '300': False})
        self.assertTrue(result['quality']['cp_comparable'])
        self.assertEqual(self.last_parsed.headers['SetUp'], '1')

    def test_missing_invalid_and_illegal_choices_remain_without_engine(self):
        cases = [('missing', None), ('malformed_response', b'\xffinvalid'),
                 ('illegal', self.response('e2e5')), ('illegal', self.response('e2e2'))]
        for expected, response in cases:
            with self.subTest(expected=expected):
                self.make_fixture([])
                self.submit('initial')
                if response is not None:
                    self.submit('final', response, seconds=20)
                with patch('chesslab.position_score.evaluator.evaluate') as engine:
                    result = self.score()
                engine.assert_not_called()
                self.assertEqual(result['final']['status'], expected)
                self.assertFalse(result['deadline_success'])
                self.assertEqual(result['quality']['status'], 'not_eligible')
                self.assertEqual(result['attempted_trials'], 1)

    def test_late_legal_quality_is_secondary_and_unknown_perception_separate(self):
        self.submit('initial')
        answer = self.response()
        answer['piece_map'] = dict.fromkeys(position_trial.SQUARES, '?')
        answer['castling'] = {s: {'kingside': 'unknown', 'queenside': 'unknown'} for s in ('white', 'black')}
        answer['en_passant_square'] = 'unknown'
        self.submit('final', answer, seconds=100)
        with patch('chesslab.position_score.evaluator.evaluate', side_effect=self.evaluation):
            result = self.score()
        self.assertFalse(result['deadline_success'])
        self.assertTrue(result['quality']['late_quality_secondary_only'])
        self.assertEqual(result['final']['transcription']['unknown_squares'], 64)
        self.assertEqual(result['final']['requested_rules']['unknown_castling_flags'], 4)
        self.assertFalse(result['final']['requested_rules']['exact_requested_rules'])

    def test_bad_raw_hash_or_feedback_is_invalid_evidence_and_not_quality(self):
        for key, value in [('response_sha256', '0' * 64), ('feedback', 'legal')]:
            with self.subTest(key=key):
                self.make_fixture([])
                self.submit('initial'); self.submit('final', seconds=20)
                path = self.trial / 'initial.json'
                record = json.loads(path.read_text()); record[key] = value
                path.write_text(json.dumps(record))
                with patch('chesslab.position_score.evaluator.evaluate') as engine:
                    result = self.score()
                engine.assert_not_called()
                self.assertEqual(result['initial']['status'], 'invalid_record')
                self.assertFalse(result['submission_records_valid'])
                self.assertFalse(result['deadline_success'])

    def test_zero_responses_and_wrong_reference_binary_never_search(self):
        with patch('chesslab.position_score.evaluator.evaluate') as engine:
            result = self.score()
        engine.assert_not_called()
        self.assertEqual(result['attempted_trials'], 1)
        self.assertFalse(result['initial']['present'])
        self.assertFalse(result['final']['present'])
        self.make_fixture([]); self.submit('initial'); self.submit('final', seconds=20)
        self.engine.write_bytes(b'different mock binary')
        with patch('chesslab.position_score.evaluator.evaluate') as engine:
            with self.assertRaisesRegex(ValueError, 'pinned engine'):
                self.score()
        engine.assert_not_called()
        self.assertTrue((self.output / 'failure.json').exists())

    def test_missing_trial_or_manifest_after_reservation_preserves_failure(self):
        for missing_trial in (True, False):
            with self.subTest(missing_trial=missing_trial):
                self.make_fixture([])
                trial = self.root / 'absent-trial' if missing_trial else self.trial
                if not missing_trial:
                    (trial / 'manifest.json').unlink()  # Temporary malformed fixture only.
                with patch('chesslab.position_score.evaluator.evaluate') as engine:
                    with self.assertRaises(FileNotFoundError):
                        scoring.score_trial(trial, self.output, actor_completed=True,
                            completion_evidence=self.completion, engine=self.engine)
                engine.assert_not_called()
                failure = json.loads((self.output / 'failure.json').read_text())
                self.assertEqual(failure['attempted_trials'], 1)
                self.assertEqual(failure['error_type'], 'FileNotFoundError')
                if not missing_trial:
                    self.assertIsNone(failure['input_hashes'][str(trial.resolve() / 'manifest.json')])
                with self.assertRaises(FileExistsError):
                    scoring.score_trial(trial, self.output, actor_completed=True,
                        completion_evidence=self.completion, engine=self.engine)

    def test_changed_input_and_reference_failure_preserve_attempts_and_partial_measurements(self):
        self.submit('initial'); self.submit('final', seconds=20)
        with patch('chesslab.position_score.evaluator.evaluate', side_effect=TimeoutError('synthetic timeout')):
            with self.assertRaises(TimeoutError):
                self.score()
        self.assertTrue(json.loads((self.output / 'measurements.json').read_text())['deadline_success'])
        self.assertEqual(json.loads((self.output / 'failure.json').read_text())['attempted_trials'], 1)
        budget = json.loads(self.corpus.with_name(self.corpus.name + '-engine-budget.json').read_text())
        self.assertEqual(budget['operations'][-1]['status'], 'failed')
        with self.assertRaises(FileExistsError):
            self.score()
        self.make_fixture([]); self.submit('initial'); self.submit('final', seconds=20)
        (self.trial / 'attachment.json').write_text('{"unplanned":"advice"}')
        with patch('chesslab.position_score.evaluator.evaluate') as engine:
            with self.assertRaisesRegex(ValueError, 'attachment_sha256'):
                self.score()
        engine.assert_not_called()
        self.assertTrue((self.output / 'failure.json').exists())

    def test_terminal_one_ply_black_pov_uses_snapshot_not_history(self):
        self.make_fixture(['f2f3', 'e7e5', 'g2g4'])
        self.submit('initial', self.response('d8h4')); self.submit('final', self.response('d8h4'), seconds=20)
        with patch('chesslab.position_score.evaluator.evaluate', side_effect=self.evaluation):
            result = self.score()
        self.assertEqual(self.last_parsed.headers['Result'], '0-1')
        self.assertTrue(self.last_parsed.final.is_checkmate())
        self.assertFalse(self.last_parsed.initial.turn)
        self.assertIn('no prior repetition', result['root_semantics'])

    def test_mates_bounds_missing_scores_and_finite_inversions_are_not_conflated(self):
        baseline = self.evaluation_without_call()
        row = baseline['engine_analysis']['rows'][0]
        for field, value, reason in [('mate', 2, 'mate_score'), ('lowerbound', True, 'bounded_score'),
                                     ('cp', None, 'missing_score')]:
            with self.subTest(reason=reason):
                evaluation = json.loads(json.dumps(baseline))
                evaluation['engine_analysis']['rows'][0]['best'][field] = value
                evaluation['engine_analysis']['rows'][0]['cp_loss_raw'] = None
                summary = scoring.quality_summary(evaluation, self.board, 'e2e4', False)
                self.assertFalse(summary['cp_comparable'])
                self.assertIn(reason, summary['cp_unavailable_reasons'])
                self.assertIsNone(summary['cp_loss_raw'])
        row['selected']['cp'] = 150; row['cp_loss_raw'] = -50
        summary = scoring.quality_summary(baseline, self.board, 'e2e4', False)
        self.assertEqual(summary['cp_loss_raw'], -50)
        self.assertEqual(summary['cp_loss_nonnegative'], 0)
        self.assertTrue(summary['finite_search_inversion'])

    def evaluation_without_call(self):
        score = lambda cp: {'cp': cp, 'mate': None, 'lowerbound': False, 'upperbound': False, 'pv': ['e2e4']}
        return {'plies': 1, 'engine_analysis': {'nodes_per_search': 100000, 'searches_per_ply': 2,
            'options': {'Threads': 1, 'Hash': 16}, 'hash_reset_each_search': True,
            'rows': [{'fen': self.board.fen(), 'turn': 'white', 'move': 'e2e4',
                      'best': score(100), 'selected': score(0), 'cp_loss_raw': 100}]}}


if __name__ == '__main__':
    unittest.main()

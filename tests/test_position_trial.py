import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import chess
except ImportError:
    chess = None

from chesslab.position_trial import prepare as prepare_raw, launch, submit, transcription_score, SQUARES, validate_response


def prepare(*args, **kwargs):
    result = prepare_raw(*args, **kwargs)
    launch(args[3])
    return result


def response():
    return {'move': 'e2e4', 'piece_map': {square: '?' for square in SQUARES},
            'side_to_move': 'white', 'confidence': .5,
            'castling': {side: {'kingside': 'unknown', 'queenside': 'unknown'} for side in ['white', 'black']},
            'en_passant_square': 'unknown'}


class ResponseTests(unittest.TestCase):
    def test_exact_unknown_and_malformed_transcription(self):
        value = response()
        self.assertEqual(transcription_score(value, {})['unknown_squares'], 64)
        value['piece_map'] = dict.fromkeys(SQUARES, '.')
        self.assertTrue(transcription_score(value, {})['exact_board'])
        del value['piece_map']['a1']
        with self.assertRaisesRegex(ValueError, 'all64'):
            validate_response(value)


@unittest.skipUnless(chess, 'post-response chess environment required')
class SubmissionTests(unittest.TestCase):
    def setUp(self):
        from chesslab.position_trial import sha
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        corpus = self.root / 'corpus'
        (corpus / 'evaluator').mkdir(parents=True)
        (corpus / 'player').mkdir()
        (corpus / 'images').mkdir()
        (corpus / 'images/fixture.png').write_bytes(b'synthetic image bytes; not an experiment')
        (corpus / 'manifest.json').write_text('{"status":"sealed","engine_work_seconds":0}')
        player = {'image': {'path': 'images/fixture.png', 'sha256': sha(corpus / 'images/fixture.png')}}
        (corpus / 'player/p001.json').write_text(json.dumps(player))
        item = {'item_id': 'p001', 'player_path': 'player/p001.json', 'fen': chess.STARTING_FEN,
                'occupancy': {chess.square_name(s): p.symbol() for s, p in chess.Board().piece_map().items()}}
        (corpus / 'evaluator/items.json').write_text(json.dumps({'items': [item]}))
        self.corpus = corpus
        self.reply = self.root / 'response.json'
        self.reply.write_text(json.dumps(response()))

    def tearDown(self):
        self.temp.cleanup()

    def test_control_has_no_oracle_and_only_legality_arm_gets_verdict(self):
        for arm in 'AC':
            directory = self.root / arm
            prepare(self.corpus, 'p001', arm, directory)
            self.assertEqual(json.loads((directory / 'attachment.json').read_text()), {})
            initial = submit(directory, 'initial', self.reply)
            self.assertEqual(initial.get('verdict'), 'legal' if arm == 'C' else None)
            with self.assertRaises(FileExistsError):
                submit(directory, 'initial', self.reply)
            final = submit(directory, 'final', self.reply)
            self.assertNotIn('verdict', final)
            with self.assertRaisesRegex(ValueError, 'final already'):
                submit(directory, 'initial', self.reply)
            with self.assertRaises(FileExistsError):
                submit(directory, 'final', self.reply)

    def test_illegal_feedback_and_state_are_declared_separately(self):
        directory = self.root / 'D'
        prepare(self.corpus, 'p001', 'D', directory)
        self.assertIn('occupancy', json.loads((directory / 'attachment.json').read_text()))
        value = response()
        value['move'] = 'e2e5'
        self.reply.write_text(json.dumps(value))
        self.assertEqual(submit(directory, 'initial', self.reply)['verdict'], 'illegal')

    def test_same_square_choice_is_preserved_as_illegal_not_dropped(self):
        directory = self.root / 'same-square'
        prepare(self.corpus, 'p001', 'C', directory)
        value = response()
        value['move'] = 'e2e2'
        self.reply.write_text(json.dumps(value))
        self.assertEqual(submit(directory, 'initial', self.reply)['verdict'], 'illegal')
        self.assertEqual(json.loads((directory / 'initial.json').read_text())['response']['move'], 'e2e2')

    def test_effort_allocation_and_supplement_boundaries(self):
        for arm, effort in [('D', 'high'), ('E', 'low'), ('F', 'low')]:
            manifest = prepare(self.corpus, 'p001', arm, self.root / arm)
            self.assertEqual(manifest['desired_reasoning'], effort)
        for arm in 'HI':
            with self.assertRaisesRegex(ValueError, 'supplement required'):
                prepare(self.corpus, 'p001', arm, self.root / arm)
        with self.assertRaisesRegex(ValueError, 'supplement required'):
            prepare(self.corpus, 'p001', 'A', self.root / 'A', supplement=self.reply)

    def test_late_and_malformed_first_submissions_are_preserved_without_feedback(self):
        from datetime import datetime, timezone
        directory = self.root / 'C'
        prepare(self.corpus, 'p001', 'C', directory)
        self.reply.write_text('{"confidence": NaN}')
        with patch('chesslab.position_trial.now', return_value=datetime(2100, 1, 1, tzinfo=timezone.utc)):
            result = submit(directory, 'initial', self.reply)
        self.assertTrue(result['late'])
        self.assertFalse(result['format_valid'])
        self.assertNotIn('verdict', result)
        saved = json.loads((directory / 'initial.json').read_text())
        self.assertIn('NaN', saved['raw_utf8'])
        self.assertIsNone(saved['response'])
        with self.assertRaises(FileExistsError):
            submit(directory, 'initial', self.reply)

    def test_changed_oracle_and_final_without_initial_are_rejected(self):
        directory = self.root / 'trial'
        prepare(self.corpus, 'p001', 'A', directory)
        with self.assertRaisesRegex(ValueError, 'initial submission required'):
            submit(directory, 'final', self.reply)
        (self.corpus / 'evaluator/items.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'evaluator_items_sha256'):
            submit(directory, 'initial', self.reply)

    def test_overflow_and_invalid_utf8_preserve_exact_first_bytes(self):
        for index, raw in enumerate((b'{"extra":1e999}', b'\xffbad-utf8')):
            directory = self.root / f'bad-{index}'
            prepare(self.corpus, 'p001', 'A', directory)
            self.reply.write_bytes(raw)
            self.assertFalse(submit(directory, 'initial', self.reply)['format_valid'])
            saved = json.loads((directory / 'initial.json').read_text())
            self.assertIsNone(saved['response'])
            self.assertEqual(base64.b64decode(saved['raw_base64']), raw)

    def test_explicit_launch_and_exclusive_preparation_precede_engine_work(self):
        directory = self.root / 'launch'
        prepared = prepare_raw(self.corpus, 'p001', 'A', directory)
        self.assertEqual(prepared['actor_seconds'], 90)
        self.assertNotIn('deadline', prepared)
        with self.assertRaises(FileNotFoundError):
            submit(directory, 'initial', self.reply)
        launched = launch(directory)
        self.assertIn('dispatch_requested_at', launched)
        with self.assertRaises(FileExistsError):
            launch(directory)
        with patch('chesslab.position_trial.bounded_recommendation') as search:
            with self.assertRaises(FileExistsError):
                prepare_raw(self.corpus, 'p001', 'G', directory, engine=self.reply)
            search.assert_not_called()

    def test_duplicate_keys_and_mutated_attachment_are_not_accepted(self):
        directory = self.root / 'duplicate'
        prepare(self.corpus, 'p001', 'A', directory)
        raw = json.dumps(response()).replace('"a1": "?"', '"a1": "?", "a1": "."')
        self.reply.write_text(raw)
        self.assertFalse(submit(directory, 'initial', self.reply)['format_valid'])
        saved = json.loads((directory / 'initial.json').read_text())
        self.assertIn('duplicate JSON key', saved['validation_error'])
        (directory / 'attachment.json').write_text('{"unplanned_advice": true}')
        with self.assertRaisesRegex(ValueError, 'attachment_sha256'):
            submit(directory, 'final', self.reply)

    def test_search_preparation_is_budgeted_and_failures_keep_reservation_evidence(self):
        async def fake_search(board, path):
            return {'move': 'e2e4', 'nodes': 2007, 'seconds': .001}, {'fixture': True}
        directory = self.root / 'search'
        with patch('chesslab.position_trial.bounded_recommendation', side_effect=fake_search):
            prepare(self.corpus, 'p001', 'G', directory, engine=self.reply)
        attachment = json.loads((directory / 'attachment.json').read_text())
        self.assertEqual(attachment['bounded_search']['nodes'], 2007)
        budget = json.loads((self.root / 'corpus-engine-budget.json').read_text())
        self.assertEqual(len(budget['operations']), 1)
        with patch('chesslab.position_trial.bounded_recommendation', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                prepare_raw(self.corpus, 'p001', 'G', self.root / 'failed-search', engine=self.reply)
        self.assertTrue((self.root / 'failed-search/preparation-failure.json').exists())
        budget = json.loads((self.root / 'corpus-engine-budget.json').read_text())
        self.assertEqual(budget['operations'][-1]['status'], 'failed')


if __name__ == '__main__':
    unittest.main()

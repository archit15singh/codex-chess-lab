from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from chesslab import diagnostic_trial as trial


def config(**extra):
    return {'trial_id': 'synthetic-001', 'purpose': 'synthetic', 'task': 'move',
            'condition': 'unaided', 'model': 'fixture-no-model', 'effort': 'none', 'seconds': 90,
            'context': {'orientation': 'white', 'rules': {'side_to_move': 'white',
                         'castling': 'KQkq', 'legal_en_passant_square': None}}, **extra}


class DiagnosticDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'fixture.png';self.image.write_bytes(b'synthetic fixture bytes, not model evidence')
        self.folder = self.root / 'trial'
        self.start = datetime(2030, 1, 1, tzinfo=timezone.utc)

    def prepare(self, value=None):
        trial.prepare(self.folder, value or config(), [self.image])
        with patch.object(trial, 'now', return_value=self.start):
            trial.launch(self.folder)

    def test_timing_boundary_and_no_overwrite(self):
        self.prepare()
        with patch.object(trial, 'now', return_value=self.start + timedelta(seconds=90)):
            result = trial.submit(self.folder, b'{"move":"a2a3"}')
        self.assertTrue(result['late'])
        self.assertTrue(result['format_valid'])
        with patch.object(trial, 'now', return_value=self.start + timedelta(seconds=91)):
            with self.assertRaises(FileExistsError):
                trial.submit(self.folder, b'{"move":"b2b3"}')
        with self.assertRaises(FileExistsError):
            trial.launch(self.folder)

    def test_malformed_response_preserved_without_chess_feedback(self):
        self.prepare()
        raw = b'{"move":"a2a3","move":"b2b3"}'
        with patch.object(trial, 'now', return_value=self.start + timedelta(seconds=1)):
            result = trial.submit(self.folder, raw)
        self.assertFalse(result['format_valid'])
        self.assertNotIn('legal', result)
        record = json.loads((self.folder / 'response.json').read_text())
        self.assertEqual(record['raw_sha256'], trial.digest(raw))
        self.assertIsNone(record['response'])

    def test_changed_inputs_fail_before_acceptance(self):
        self.prepare()
        next(self.folder.glob('image-*')).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'input changed'):
            trial.submit(self.folder, b'{"move":"a2a3"}')
        self.assertFalse((self.folder / 'response.json').exists())

    def test_clock_extension_is_rejected(self):
        self.prepare()
        clock = json.loads((self.folder / 'clock.json').read_text())
        clock['deadline'] = (self.start + timedelta(seconds=900)).isoformat()
        (self.folder / 'clock.json').write_text(json.dumps(clock))
        with patch.object(trial, 'now', return_value=self.start + timedelta(seconds=100)):
            with self.assertRaisesRegex(ValueError, 'clock provenance'):
                trial.submit(self.folder, b'{"move":"a2a3"}')

    def test_saved_response_readback_rejects_flag_and_payload_mutation(self):
        self.prepare()
        with patch.object(trial, 'now', return_value=self.start + timedelta(seconds=1)):
            trial.submit(self.folder, b'{"move":"a2a3"}')
        record = trial.read_result(self.folder)
        path = self.folder / 'response.json'
        changed = deepcopy(record);changed['late'] = True
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'timing'):
            trial.read_result(self.folder)
        changed = deepcopy(record);changed['response']['move'] = 'b2b3'
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'preserved bytes'):
            trial.read_result(self.folder)

    def test_information_attachment_requires_assigned_condition(self):
        c = config();c['context']['validated_state'] = {s: '.' for s in trial.SQUARES}
        with self.assertRaisesRegex(ValueError, 'unassigned information'):
            trial.prepare(self.folder, c, [self.image])
        c['condition'] = 'state'
        trial.prepare(self.folder, c, [self.image])
        self.assertTrue(trial.verify(self.folder))

    def test_history_and_perception_formats_do_not_evaluate_truth(self):
        c = config(task='history');c['context']['query'] = {'checkpoint_ply': 1, 'squares': ['b1', 'g1']}
        self.assertTrue(trial.response_format({'recall': {'b1': '?', 'g1': '.'}}, c))
        self.assertFalse(trial.response_format({'recall': {'b1': '.'}}, c))
        c = config(task='perception')
        self.assertTrue(trial.response_format({'move': 'a1a1', 'piece_map': {s: '?' for s in trial.SQUARES}}, c))
        self.assertFalse(trial.response_format({'move': 'a1a1'}, c))

    def test_history_packet_preserves_checkpoint_labels(self):
        c = config(task='history');c['context']['query'] = {'checkpoint_ply': 1, 'squares': ['b1', 'g1']}
        with self.assertRaisesRegex(ValueError, 'checkpoint labels'):
            trial.prepare(self.folder, c, [self.image, self.image])
        trial.prepare(self.folder, c, [self.image, self.image], image_plies=[1, 4])
        packet = json.loads((self.folder / 'input.json').read_text())
        exposure = json.loads((self.folder / 'exposure.json').read_text())
        self.assertEqual([i['ply'] for i in packet['images']], [4])
        self.assertEqual([i['ply'] for i in exposure['images']], [1])
        self.assertNotIn('query', exposure)
        past = exposure['images'][0]['path']
        self.assertNotIn(past, (self.folder / 'input.json').read_text())
        with self.assertRaises(FileNotFoundError):
            trial.launch(self.folder, actor_thread_id='actor-original')
        proof = self.root / 'host-completion.json'
        proof.write_text('{"scope":"synthetic host proof fixture only"}')
        trial.record_exposure(self.folder, 'actor-original', 'exposure-turn', proof)
        with self.assertRaisesRegex(ValueError, 'same actor'):
            trial.launch(self.folder, actor_thread_id='replacement')
        with patch.object(trial, 'now', return_value=self.start):
            trial.launch(self.folder, actor_thread_id='actor-original')
        with patch.object(trial, 'now', return_value=self.start + timedelta(seconds=1)):
            trial.submit(self.folder, b'{"recall":{"b1":"N","g1":"."}}')
        self.assertTrue(trial.read_result(self.folder)['format_valid'])


if __name__ == '__main__':
    unittest.main()

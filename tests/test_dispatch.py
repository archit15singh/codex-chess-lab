import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from chesslab.dispatch import dispatch


class DispatchTests(unittest.TestCase):
    def test_unknown_placeholder_fails_before_clock_starts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'manifest.json').write_text('{"image_path":"image","player_path":"player","desired_model":"fixture","desired_reasoning":"high"}')
            template = root / 'template.txt'
            template.write_text('{{UNEXPECTED}}')
            with patch('chesslab.dispatch.launch') as clock:
                with self.assertRaisesRegex(ValueError, 'clock not started'):
                    dispatch(root, template, root, Path(sys.executable))
                clock.assert_not_called()

    def test_frozen_mechanics_checked_and_brief_complete_at_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / 'runtime'
            (runtime / 'chesslab').mkdir(parents=True)
            source = runtime / 'chesslab/position_trial.py'
            source.write_bytes(b'synthetic mechanics fixture')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            (runtime / 'manifest.json').write_text(json.dumps({'files': {'chesslab/position_trial.py': digest}}))
            manifest = {'image_path': 'image', 'player_path': 'player', 'source_sha256': digest,
                        'desired_model': 'fixture', 'desired_reasoning': 'high'}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            template = root / 'template.txt'
            template.write_text('PRIVATE TEMPLATE ONLY. {{PLACEHOLDER}}\n{{TRIAL_ID}} {{CHOSEN_UCI_MOVE}} {{LAUNCH_RECORDED_AT_UTC}} {{DEADLINE_UTC}}')
            with patch('chesslab.dispatch.launch', return_value={'dispatch_requested_at': 'start', 'deadline': 'end'}) as clock:
                with self.assertRaisesRegex(ValueError, 'executable Python'):
                    dispatch(root, template, runtime, Path('/definitely/missing/python'))
                clock.assert_not_called()
                (root / 'manifest.json').write_text(json.dumps({k: v for k, v in manifest.items() if k != 'desired_model'}))
                with self.assertRaisesRegex(ValueError, 'model and effort'):
                    dispatch(root, template, runtime, Path(sys.executable))
                clock.assert_not_called()
                (root / 'manifest.json').write_text(json.dumps(manifest))
                result = dispatch(root, template, runtime, Path(sys.executable))
                clock.assert_called_once_with(root.resolve())
            self.assertEqual((root / 'actor-brief.txt').read_text(), root.name + ' <your UCI choice> start end')
            self.assertEqual(result['deadline'], 'end')
            with patch('chesslab.dispatch.launch') as clock:
                with self.assertRaises(FileExistsError):
                    dispatch(root, template, runtime, Path(sys.executable))
                clock.assert_not_called()


if __name__ == '__main__':
    unittest.main()

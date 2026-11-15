"""Synthetic accounting checks only; no engine or study corpus is run."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chesslab.engine_budget import engine_allowance


class EngineBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.temp.name) / 'synthetic-corpus'
        self.corpus.mkdir()
        self.manifest = self.corpus / 'manifest.json'
        self.manifest.write_text(json.dumps({'status': 'sealed', 'engine_work_seconds': 100.0}))
        self.budget = self.corpus.parent / 'synthetic-corpus-engine-budget.json'

    def tearDown(self):
        self.temp.cleanup()

    def state(self):
        return json.loads(self.budget.read_bytes())

    def test_initial_generation_deduction_durable_reservation_and_lock(self):
        with (patch('chesslab.engine_budget.time.monotonic', side_effect=[10.0, 12.5]),
              patch('chesslab.engine_budget.os.fsync', wraps=os.fsync) as sync):
            with engine_allowance(self.corpus, 'synthetic-query', 13) as allowance:
                self.assertEqual(allowance.allowed_seconds, 13)
                self.assertEqual(allowance.charged_before_seconds, 100)
                self.assertEqual(allowance.remaining_seconds, 1687)
                self.assertEqual(allowance.budget_path, self.budget.resolve())
                saved = self.state()
                self.assertEqual(saved['charged_seconds'], 113)
                self.assertEqual(saved['operations'][0]['status'], 'reserved')
                self.assertEqual(sync.call_count, 3)  # Initial state, directory, reservation.
                with self.budget.open('r') as second:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = self.state()
        self.assertEqual(state['charged_seconds'], 102.5)
        self.assertEqual(state['operations'][0]['status'], 'completed')
        self.assertEqual(state['operations'][0]['actual_seconds'], 2.5)

    def test_failure_is_charged_and_original_exception_propagates(self):
        with patch('chesslab.engine_budget.time.monotonic', side_effect=[5.0, 8.0]):
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                with engine_allowance(self.corpus, 'synthetic-failure', 13):
                    raise RuntimeError('synthetic failure')
        state = self.state()
        self.assertEqual(state['charged_seconds'], 103)
        self.assertEqual(state['operations'][0]['status'], 'failed')
        self.assertEqual(state['operations'][0]['failure_type'], 'RuntimeError')

    def test_process_crash_keeps_full_charge_and_reuse_is_cumulative(self):
        script = '''
import os
from pathlib import Path
import sys
from chesslab.engine_budget import engine_allowance
with engine_allowance(Path(sys.argv[1]), 'synthetic-crash', 13):
    os._exit(0)
'''
        completed = subprocess.run([sys.executable, '-c', script, str(self.corpus)],
                                   cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(self.state()['charged_seconds'], 113)
        self.assertEqual(self.state()['operations'][0]['status'], 'reserved')
        with patch('chesslab.engine_budget.time.monotonic', side_effect=[10, 14]):
            with engine_allowance(self.corpus, 'synthetic-recovery', 13) as allowance:
                self.assertEqual(allowance.charged_before_seconds, 113)
                self.assertEqual(self.state()['charged_seconds'], 126)
        self.assertEqual(self.state()['charged_seconds'], 117)
        self.assertEqual(len(self.state()['operations']), 2)

    def test_insufficient_budget_refuses_full_reservation(self):
        self.manifest.write_text(json.dumps({'status': 'sealed', 'engine_work_seconds': 1790}))
        with self.assertRaisesRegex(ValueError, 'insufficient'):
            with engine_allowance(self.corpus, 'must-not-start', 13):
                self.fail('operation entered')
        self.assertEqual(self.state()['charged_seconds'], 1790)
        self.assertEqual(self.state()['operations'], [])

    def test_existing_empty_or_corrupt_or_inconsistent_budget_never_resets(self):
        for raw in (b'', b'{broken', b'{}', b'[]'):
            with self.subTest(raw=raw):
                self.budget.write_bytes(raw)
                with self.assertRaises(ValueError):
                    with engine_allowance(self.corpus, 'must-not-start', 13):
                        self.fail('operation entered')
                self.assertEqual(self.budget.read_bytes(), raw)
        self.budget.unlink()  # Only this temporary malformed test fixture.
        with patch('chesslab.engine_budget.time.monotonic', side_effect=[0, 1]):
            with engine_allowance(self.corpus, 'fixture', 13):
                pass
        state = self.state()
        state['charged_seconds'] = 0
        self.budget.write_text(json.dumps(state))
        snapshot = self.budget.read_bytes()
        with self.assertRaisesRegex(ValueError, 'total differs'):
            with engine_allowance(self.corpus, 'must-not-start', 13):
                self.fail('operation entered')
        self.assertEqual(self.budget.read_bytes(), snapshot)

    def test_manifest_change_refused_without_reset(self):
        with patch('chesslab.engine_budget.time.monotonic', side_effect=[0, 1]):
            with engine_allowance(self.corpus, 'fixture', 13):
                pass
        snapshot = self.budget.read_bytes()
        self.manifest.write_text(json.dumps({'status': 'sealed', 'engine_work_seconds': 0}))
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            with engine_allowance(self.corpus, 'must-not-start', 13):
                self.fail('operation entered')
        self.assertEqual(self.budget.read_bytes(), snapshot)

    def test_overrun_is_charged_in_full_and_blocks_future_work(self):
        self.manifest.write_text(json.dumps({'status': 'sealed', 'engine_work_seconds': 1780}))
        with patch('chesslab.engine_budget.time.monotonic', side_effect=[0, 25]):
            with self.assertRaisesRegex(TimeoutError, 'exceeded its reserved'):
                with engine_allowance(self.corpus, 'overrun', 13):
                    pass
        self.assertEqual(self.state()['charged_seconds'], 1805)
        self.assertTrue(self.state()['operations'][0]['reservation_overrun'])
        self.assertEqual(self.state()['operations'][0]['status'], 'failed')
        with self.assertRaisesRegex(ValueError, 'insufficient'):
            with engine_allowance(self.corpus, 'must-not-start', 13):
                self.fail('operation entered')

    def test_overrun_preserves_original_body_exception(self):
        with patch('chesslab.engine_budget.time.monotonic', side_effect=[0, 25]):
            with self.assertRaisesRegex(RuntimeError, 'original failure'):
                with engine_allowance(self.corpus, 'failed-overrun', 13):
                    raise RuntimeError('original failure')
        self.assertEqual(self.state()['charged_seconds'], 125)
        self.assertTrue(self.state()['operations'][0]['reservation_overrun'])
        self.assertEqual(self.state()['operations'][0]['failure_type'], 'RuntimeError')

    def test_unsealed_manifest_and_invalid_limits_are_refused(self):
        for invalid in (0, -1, float('inf'), float('nan'), True, '13'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                with engine_allowance(self.corpus, 'fixture', invalid):
                    self.fail('operation entered')
        self.assertFalse(self.budget.exists())
        self.manifest.write_text(json.dumps({'status': 'building', 'engine_work_seconds': 0}))
        with self.assertRaisesRegex(ValueError, 'sealed'):
            with engine_allowance(self.corpus, 'must-not-start', 13):
                self.fail('operation entered')


if __name__ == '__main__':
    unittest.main()

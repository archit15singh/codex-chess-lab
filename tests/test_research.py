import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from chesslab.ledger import Ledger
from chesslab.stats import summarize, wilson

HASH = 'a' * 64


def config():
    return json.loads(Path('configs/feasibility.json').read_text())


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'runs.sqlite'
        self.ledger = Ledger(self.path)
        self.ledger.create('a', config())

    def tearDown(self):
        self.ledger.db.close()
        self.tmp.cleanup()

    def intent(self, action='1'):
        self.ledger.append('a', 'intent', {'action_id': action, 'move': 'e2e4', 'screenshot_sha256': HASH})

    def verify(self, outcome='executed'):
        self.ledger.append('a', 'verification', {'action_id': '1', 'outcome': outcome, 'screenshot_sha256': HASH})

    def test_duplicate_and_inflight_block_after_restart(self):
        self.intent()
        other = Ledger(self.path)
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            other.append('a', 'intent', {'action_id': '2', 'move': 'e2e4', 'screenshot_sha256': HASH})
        other.db.close()
        self.verify()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.intent()

    def test_uncertainty_keeps_action_pending(self):
        self.intent()
        self.verify('uncertain')
        self.assertEqual(self.ledger.events('a')[-1]['payload']['outcome'], 'uncertain')
        other = Ledger(self.path)
        try:
            with self.assertRaisesRegex(ValueError, 'unresolved'):
                other.append('a', 'intent', {'action_id': '2', 'move': 'e2e4', 'screenshot_sha256': HASH})
            with self.assertRaisesRegex(ValueError, 'resolve'):
                other.append('a', 'terminal', {'result': 'aborted', 'screenshot_sha256': HASH})
        finally:
            other.db.close()
        self.verify('not_executed')
        outcomes = [e['payload']['outcome'] for e in self.ledger.events('a')
                    if e['kind'] == 'verification']
        self.assertEqual(outcomes, ['uncertain', 'not_executed'])
        self.intent('2')

    def test_prohibited_capability_and_mutation(self):
        with self.assertRaisesRegex(ValueError, 'prohibited'):
            self.ledger.append('a', 'tool', {'capability': 'search'})
        self.ledger.append('a', 'tool', {'capability': 'screenshot'})
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.db.execute('DELETE FROM events')
        self.ledger.db.rollback()

    def test_baseline_and_metadata(self):
        c = config()
        c['capabilities'].append('legality')
        with self.assertRaisesRegex(ValueError, 'unaided'):
            self.ledger.create('b', c)
        c = config()
        del c['model']
        with self.assertRaises(ValueError):
            self.ledger.create('b', c)

    def test_terminal_is_final(self):
        self.intent()
        with self.assertRaisesRegex(ValueError, 'resolve'):
            self.ledger.append('a', 'terminal', {'result': 'win', 'screenshot_sha256': HASH})
        self.verify()
        self.ledger.append('a', 'terminal', {'result': 'win', 'screenshot_sha256': HASH})
        with self.assertRaisesRegex(ValueError, 'terminal'):
            self.intent('2')
        self.assertEqual(len(self.ledger.export('a')['events']), 3)

    def test_bad_hash_and_mismatched_verification(self):
        with self.assertRaises(ValueError):
            self.ledger.append('a', 'intent', {'action_id': '1', 'move': 'e2e4', 'screenshot_sha256': 'bad'})
        with self.assertRaises(ValueError):
            self.verify()
        self.assertEqual(self.ledger.events('a'), [])


class StatsTests(unittest.TestCase):
    def test_reference_values(self):
        self.assertIsNone(wilson(0, 0))
        low, high = wilson(5, 10)
        self.assertAlmostEqual(low, .2365930905)
        self.assertAlmostEqual(high, .7634069095)
        self.assertAlmostEqual(wilson(0, 10)[1], .2775327999)
        with self.assertRaises(ValueError):
            wilson(11, 10)

    def test_pending_harness_stop_is_aborted_not_a_game_result(self):
        run = {'run': 'stopped', 'config': config(), 'events': [
            {'kind': 'observation', 'payload': {'record_type': 'harness_stop', 'pending_action_id': '1'}}]}
        result = summarize([run])
        self.assertEqual(result['aborted'], 1)
        self.assertEqual(result['completed'], 0)
        self.assertIsNone(result['score_completed'])

    def test_stop_and_terminal_conflict_requires_review(self):
        run = {'run': 'conflict', 'config': config(), 'events': [
            {'kind': 'observation', 'payload': {'record_type': 'harness_stop'}},
            {'kind': 'terminal', 'payload': {'result': 'win'}}]}
        with self.assertRaisesRegex(ValueError, 'conflicting harness stop'):
            summarize([run])

    def test_empty_is_not_zero_performance(self):
        result = summarize([])
        self.assertIsNone(result['completion_ci95'])
        self.assertIsNone(result['score_completed'])
        self.assertIsNone(result['rating'])

    def test_missing_games_and_synthetic_exclusion(self):
        a = {'run': 'a', 'config': config(), 'events': []}
        b = {'run': 'b', 'config': config(), 'events': [{'kind': 'terminal', 'payload': {'result': 'win'}}]}
        result = summarize([a, b])
        self.assertEqual(result['started'], 2)
        self.assertEqual(result['completed'], 1)
        self.assertEqual(result['incomplete'], 1)
        with self.assertRaises(ValueError):
            summarize([a, a])
        a['config']['purpose'] = 'synthetic'
        with self.assertRaisesRegex(ValueError, 'synthetic'):
            summarize([a])

    def test_analysis_identity_must_match(self):
        a = {'run': 'a', 'config': config(), 'events': []}
        variants = {'condition': 'state', 'model': 'other-model',
                    'reasoning': 'other-budget', 'purpose': 'heldout',
                    'capabilities': ['screenshot', 'coordinate_click', 'history']}
        for field, value in variants.items():
            with self.subTest(field=field):
                b = {'run': 'b', 'config': config(), 'events': []}
                b['config'][field] = value
                with self.assertRaisesRegex(ValueError, 'analysis identity'):
                    summarize([a, b])

    def test_replicate_seeds_and_capability_order_can_vary(self):
        a = {'run': 'a', 'config': config(), 'events': []}
        b = {'run': 'b', 'config': config(), 'events': []}
        b['config']['seed'] += 1
        b['config']['capabilities'].reverse()
        result = summarize([a, b])
        self.assertEqual(result['started'], 2)
        self.assertEqual(result['incomplete'], 2)

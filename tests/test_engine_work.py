"""Synthetic accounting tests; no model assignments or engine searches."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from chesslab.engine_work import create, reserve, settle, summary, nanoseconds


class EngineWorkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'budget.sqlite'
        create(self.path, 10, provenance={'protocol': 'synthetic fixture'})

    def receipt(self, name, active, stopped=True):
        path = self.root / name
        path.write_text(json.dumps({'active_ns': active, 'process_stopped': stopped}))
        return path

    def test_pending_full_charge_and_measured_refund_after_exit(self):
        reserve(self.path, 'one', 7, metadata={'purpose': 'fixture'})
        self.assertEqual(summary(self.path)['remaining_ns'], 3_000_000_000)
        with self.assertRaises(ValueError):
            reserve(self.path, 'two', 4, metadata={'purpose': 'fixture'})
        settle(self.path, 'one', 2_000_000_001, receipt=self.receipt('proof', 2_000_000_001))
        self.assertEqual(summary(self.path)['charged_ns'], 2_000_000_001)
        reserve(self.path, 'two', 7, metadata={'purpose': 'fixture'})

    def test_unknown_exit_cannot_refund_and_receipt_cannot_change(self):
        reserve(self.path, 'one', 4, metadata={'purpose': 'fixture'})
        bad = self.receipt('bad', 1, stopped=False)
        with self.assertRaises(ValueError): settle(self.path, 'one', 1, receipt=bad)
        self.assertEqual(summary(self.path)['charged_ns'], 4_000_000_000)
        good = self.receipt('good', 2)
        settle(self.path, 'one', 2, receipt=good)
        good.write_text('{}')
        with self.assertRaises(ValueError): summary(self.path)
        with self.assertRaises(ValueError): reserve(self.path, 'two', 1, metadata={'purpose': 'fixture'})

    def test_overrun_is_charged_before_exception_and_blocks_cap(self):
        reserve(self.path, 'one', 1, metadata={'purpose': 'fixture'})
        with self.assertRaises(TimeoutError):
            settle(self.path, 'one', 11_000_000_000, receipt=self.receipt('proof', 11_000_000_000))
        state = summary(self.path)
        self.assertEqual(state['charged_ns'], 11_000_000_000)
        self.assertTrue(state['over_cap'])
        self.assertTrue(state['operations'][0]['overrun'])
        with self.assertRaises(ValueError): reserve(self.path, 'two', 1, metadata={'purpose': 'fixture'})

    def test_duplicates_missing_database_and_append_only_guards(self):
        with self.assertRaises(FileExistsError): create(self.path, provenance={'reason': 'never reset'})
        with self.assertRaises(sqlite3.OperationalError): summary(self.root / 'missing')
        reserve(self.path, 'one', 1, metadata={'purpose': 'fixture'})
        with self.assertRaises(sqlite3.IntegrityError): reserve(self.path, 'one', 1, metadata={'purpose': 'fixture'})
        proof = self.receipt('proof', 0)
        settle(self.path, 'one', 0, receipt=proof)
        with self.assertRaises(sqlite3.IntegrityError): settle(self.path, 'one', 0, receipt=proof)
        with self.assertRaises(ValueError): settle(self.path, 'unknown', 0, receipt=proof)
        with closing(sqlite3.connect(self.path)) as db:
            for query in ['DELETE FROM reservations', 'UPDATE settlements SET active_ns=0',
                          'UPDATE policy SET limit_ns=999', "INSERT INTO policy VALUES (99, '{}')"]:
                with self.subTest(query=query), self.assertRaises(sqlite3.IntegrityError): db.execute(query)

    def test_atomic_thirty_way_reservations_do_not_exceed_cap(self):
        def attempt(i):
            try:
                reserve(self.path, f'operation-{i}', 1, metadata={'purpose': 'race fixture'})
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=10) as pool:
            accepted = list(pool.map(attempt, range(30)))
        self.assertEqual(sum(accepted), 10)
        self.assertEqual(summary(self.path)['charged_ns'], 10_000_000_000)

    def test_numeric_guards_and_conservative_nanosecond_rounding(self):
        self.assertEqual(nanoseconds('0.0000000001'), 1)
        for value in [True, False, 0, -1, 'NaN', float('inf'), 'oops', 86401, None]:
            with self.subTest(value=value), self.assertRaises(ValueError): nanoseconds(value)
        reserve(self.path, 'one', 1, metadata={'purpose': 'fixture'})
        for value in [True, -1, 1.5, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                settle(self.path, 'one', value, receipt=self.root / 'absent')


if __name__ == '__main__':
    unittest.main()

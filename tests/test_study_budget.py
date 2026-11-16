import concurrent.futures
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from chesslab import study_budget as budget


class StudyBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'budget.sqlite'

    def test_pilot_and_total_reservations_are_atomic(self):
        budget.create(self.path, {'games': 3, 'pilot_games': 1})
        budget.reserve(self.path, 'pilot-1', {'games': 1, 'pilot_games': 1})
        with self.assertRaisesRegex(ValueError, 'cap'):
            budget.reserve(self.path, 'pilot-2', {'games': 1, 'pilot_games': 1})
        self.assertEqual(budget.summary(self.path)['used'], {'games': 1, 'pilot_games': 1})
        budget.reserve(self.path, 'final-1', {'games': 1})
        self.assertEqual(budget.summary(self.path)['used']['games'], 2)

    def test_concurrent_reservations_cannot_oversubscribe(self):
        budget.create(self.path, {'diagnostics': 1})
        def attempt(identity):
            try:
                budget.reserve(self.path, identity, {'diagnostics': 1})
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ['a', 'b']))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(budget.summary(self.path)['used']['diagnostics'], 1)

    def test_existing_or_missing_ledger_cannot_silently_reset(self):
        with self.assertRaises(sqlite3.OperationalError):
            budget.summary(self.path)
        self.assertFalse(self.path.exists())
        budget.create(self.path)
        budget.reserve(self.path, 'failed-launch', {'games': 1})
        with self.assertRaises(FileExistsError):
            budget.create(self.path)
        self.assertEqual(budget.summary(self.path)['used']['games'], 1)

    def test_duplicate_ids_and_mutation_are_rejected(self):
        budget.create(self.path, {'games': 3})
        budget.reserve(self.path, 'game-1', {'games': 1})
        with self.assertRaises(sqlite3.IntegrityError):
            budget.reserve(self.path, 'game-1', {'games': 1})
        with closing(sqlite3.connect(self.path)) as db:
            for sql in ['UPDATE limits SET amount=99', 'DELETE FROM limits',
                        "INSERT INTO limits VALUES ('new',99)",
                        "UPDATE reservations SET usage='{}'", 'DELETE FROM reservations']:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
        self.assertEqual(budget.summary(self.path)['used']['games'], 1)

    def test_invalid_counts_and_unknown_resources_fail_closed(self):
        budget.create(self.path, {'games': 2})
        for usage in [{}, {'games': True}, {'games': 1.5}, {'games': -1},
                      {'games': 0}, {'gamez': 1}]:
            with self.assertRaises(ValueError):
                budget.reserve(self.path, 'bad', usage)
        self.assertEqual(budget.summary(self.path)['used']['games'], 0)

    def test_pilot_usage_cannot_bypass_total_cap(self):
        budget.create(self.path)
        with self.assertRaisesRegex(ValueError, 'total cap'):
            budget.reserve(self.path, 'pilot-bypass', {'pilot_games': 1})
        self.assertEqual(budget.summary(self.path)['used']['pilot_games'], 0)


if __name__ == '__main__':
    unittest.main()

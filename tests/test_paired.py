import copy
import unittest

from chesslab.paired import paired_summary


def row(unit, family, a, b, c=0):
    return {'unit': unit, 'family': family, 'values': {'A': a, 'B': b, 'C': c}}


class PairedTests(unittest.TestCase):
    def test_family_weighting_not_move_weighting(self):
        rows = [row('a', 'large', 0, 10), row('b', 'large', 0, 10), row('c', 'small', 0, 0)]
        result = paired_summary(rows, ['A', 'B', 'C'], resamples=500)
        contrast = result['contrasts'][0]
        self.assertEqual(contrast['estimate'], 5)
        self.assertEqual(contrast['bootstrap_percentile95'], [0, 10])
        self.assertEqual(contrast['leave_one_family_out'], {'large': 0, 'small': 10})
        self.assertEqual(result, paired_summary(rows, ['A', 'B', 'C'], resamples=500))

    def test_shared_complete_cohort_and_failure_coverage(self):
        rows = [row('a', 'f1', 0, 2, None), row('b', 'f2', None, 9, 3), row('c', 'f2', 0, 4, 8)]
        result = paired_summary(rows, ['A', 'B', 'C'], resamples=20)
        self.assertEqual(result['assigned_units'], 3)
        self.assertEqual(result['available_units_by_arm'], {'A': 2, 'B': 3, 'C': 2})
        self.assertEqual(result['common_units'], 1)
        self.assertEqual(result['families_without_common_units'], ['f1'])
        self.assertEqual([c['estimate'] for c in result['contrasts']], [4, 8, 4])

    def test_no_data_and_single_cluster_remain_explicit(self):
        result = paired_summary([row('a', 'f1', None, None, None)], ['A', 'B', 'C'])
        self.assertEqual(result['common_families'], 0)
        self.assertIsNone(result['contrasts'][0]['estimate'])
        self.assertIsNone(result['contrasts'][0]['bootstrap_percentile95'])
        result = paired_summary([row('a', 'f1', 0, 2, 4)], ['A', 'B', 'C'], resamples=5)
        self.assertEqual(result['contrasts'][0]['leave_one_family_out'], {'f1': None})

    def test_exact_sign_flip_six_positive_families(self):
        rows = [row(str(i), str(i), 0, i + 1) for i in range(6)]
        result = paired_summary(rows, ['A', 'B', 'C'], resamples=20)
        ref = result['contrasts'][0]['sign_flip_reference']
        self.assertEqual(ref['assignments'], 64)
        self.assertEqual(ref['two_sided_p'], 2 / 64)

    def test_input_integrity(self):
        good = [row('a', 'f1', 0, 2)]
        for bad in [good * 2, [row('a', 'f1', float('nan'), 0)],
                    [row('a', 'f1', True, 0)], []]:
            with self.assertRaises(ValueError):
                paired_summary(bad, ['A', 'B', 'C'])
        bad = copy.deepcopy(good)
        del bad[0]['values']['C']
        with self.assertRaises(ValueError):
            paired_summary(bad, ['A', 'B', 'C'])
        with self.assertRaises(ValueError):
            paired_summary(good, ['A', 'A'])


if __name__ == '__main__':
    unittest.main()

from decimal import Decimal
from fractions import Fraction
from itertools import product
import random
import unittest

from chesslab.grouped_reference import exact_reference, sign_counts, holm
from scripts.exact_reference import exact_reference as legacy_reference


class GroupedReferenceTests(unittest.TestCase):
    def test_twentyfour_families_closed_form_and_ties(self):
        positive = sign_counts([1] * 24)
        self.assertEqual(positive['assignments'], 2**24)
        self.assertEqual(positive['states'], 25)
        self.assertEqual(positive['positive_inclusive_tail'], 1)
        self.assertEqual(positive['negative_inclusive_tail'], 2**24)
        self.assertEqual(positive['two_sided_inclusive_tail'], 2)
        zero = sign_counts([0] * 24)
        self.assertEqual(zero['states'], 1)
        self.assertEqual(zero['positive_inclusive_tail'], 2**24)
        self.assertEqual(zero['two_sided_p_exact'], '1')
        negative = sign_counts([-1] * 24)
        self.assertEqual(negative['positive_p_exact'], '1')
        self.assertEqual(negative['negative_inclusive_tail'], 1)

    def test_exact_decimal_inclusive_tails_match_independent_enumeration(self):
        rng = random.Random(1947)
        for n in range(1, 10):
            for _ in range(10):
                values = [Fraction(rng.randrange(-4, 5), 10) for _ in range(n)]
                observed = sum(values)
                possibilities = [sum(sign * value for sign, value in zip(signs, values))
                                 for signs in product([-1, 1], repeat=n)]
                result = sign_counts(values)
                self.assertEqual(result['positive_inclusive_tail'], sum(v >= observed for v in possibilities))
                self.assertEqual(result['negative_inclusive_tail'], sum(v <= observed for v in possibilities))
                self.assertEqual(result['two_sided_inclusive_tail'], sum(abs(v) >= abs(observed) for v in possibilities))
        values = [Decimal('0.1'), Decimal('0.2'), Decimal('-0.3')]
        self.assertEqual(sign_counts(values)['positive_inclusive_tail'], 5)

    def test_family_weighting_and_historical_exact_crosscheck(self):
        rows = [{'unit': 'a1', 'family': 'a', 'values': {'base': 0, 'candidate': 1}},
                {'unit': 'a2', 'family': 'a', 'values': {'base': 1, 'candidate': 1}},
                {'unit': 'b1', 'family': 'b', 'values': {'base': 1, 'candidate': 0}}]
        result = exact_reference(rows, ['base', 'candidate'])
        contrast = result['contrasts'][0]
        self.assertEqual(contrast['estimate_exact'], '-1/4')
        self.assertEqual(contrast['family_differences_exact'], {'a': '1/2', 'b': '-1'})
        old = legacy_reference(rows, ['base', 'candidate'])
        self.assertEqual(contrast['sign_flip']['two_sided_inclusive_tail'], old['contrasts'][0]['inclusive_tail_assignments'])

    def test_all_arm_common_cohort_and_empty_families_remain_explicit(self):
        rows = [{'unit': 'a1', 'family': 'a', 'values': {'base': 0, 'sham': None, 'candidate': 1}},
                {'unit': 'a2', 'family': 'a', 'values': {'base': 1, 'sham': 1, 'candidate': 1}},
                {'unit': 'b1', 'family': 'b', 'values': {'base': 0, 'sham': 0, 'candidate': 1}},
                {'unit': 'c1', 'family': 'c', 'values': {'base': None, 'sham': 0, 'candidate': 0}}]
        result = exact_reference(rows, ['base', 'sham', 'candidate'])
        self.assertEqual(result['assigned_units'], 4)
        self.assertEqual(result['assigned_families'], 3)
        self.assertEqual(result['common_units'], 2)
        self.assertEqual(result['common_families'], 2)
        self.assertEqual(result['unmatched_units'], ['a1', 'c1'])
        self.assertEqual(result['families_without_common_units'], ['c'])
        self.assertEqual(result['contrasts'][1]['estimate_exact'], '1/2')
        empty = exact_reference(rows[:1], ['base', 'sham', 'candidate'])
        self.assertIsNone(empty['contrasts'][0]['estimate_exact'])
        self.assertIsNone(empty['contrasts'][0]['sign_flip'])

    def test_holm_exact_boundaries_ties_and_stepdown(self):
        result = holm([{'id': 'a', 'tail': 1, 'assignments': 40},
                       {'id': 'b', 'tail': 1, 'assignments': 20}])
        self.assertTrue(all(row['reject'] for row in result['results']))
        self.assertEqual([row['adjusted_p_exact'] for row in result['results']], ['1/20', '1/20'])
        result = holm([{'id': 'a', 'tail': 26, 'assignments': 1000},
                       {'id': 'b', 'tail': 26, 'assignments': 1000}])
        self.assertFalse(any(row['reject'] for row in result['results']))
        self.assertEqual(result['results'][1]['adjusted_p_exact'], '13/250')

    def test_invalid_values_and_bounded_computation_fail_without_rounding(self):
        for values in [[], [True], [float('nan')], ['0.5']]:
            with self.subTest(values=values), self.assertRaises(ValueError): sign_counts(values)
        with self.assertRaisesRegex(ValueError, 'state limit'):
            sign_counts([1, 2, 4, 8], state_limit=4)
        with self.assertRaisesRegex(ValueError, 'precision limit'):
            sign_counts([Decimal('1e-100000000')])
        with self.assertRaisesRegex(ValueError, 'scale precision limit'):
            sign_counts([Fraction(1, 2**257-1), Fraction(1, 2**263-1)])
        for rows, arms in [
            ([{'unit': 'x', 'family': 'f', 'values': {'a': 0, 'b': 2}}], ['a', 'b']),
            ([{'unit': 'x', 'family': 'f', 'values': {'a': 0, 'b': 1}}] * 2, ['a', 'b']),
            ([{'unit': 'x', 'family': 'f', 'values': {'a': 0, 'b': 1}}], ['a', {}])]:
            with self.subTest(rows=rows, arms=arms), self.assertRaises(ValueError): exact_reference(rows, arms)
        with self.assertRaises(ValueError): holm([{'id': 'a', 'tail': True, 'assignments': 2}])


if __name__ == '__main__':
    unittest.main()

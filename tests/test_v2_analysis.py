from copy import deepcopy
from fractions import Fraction
import unittest

from chesslab.v2_analysis import bootstrap_plan, family_summary, hoeffding, project_plan, promotion


def primary():
    return [{'unit': f'f{family}-i{item}', 'family': f'f{family}',
             'values': {'baseline': 0, 'sham': 0, 'candidate': 1}}
            for family in range(24) for item in range(2)]


def costs():
    return {arm: [100] * 48 for arm in ('baseline', 'sham', 'candidate')}


class V2AnalysisTests(unittest.TestCase):
    def test_stratified_shared_draws_preserve_linked_cohort_and_determinism(self):
        families = [f'a{i}' for i in range(12)] + [f'b{i}' for i in range(12)]
        strata = [families[:12], families[12:]]
        plan = bootstrap_plan(families, strata=strata, resamples=100)
        self.assertEqual(plan, bootstrap_plan(families, strata=strata, resamples=100))
        first = project_plan(plan, families[:12])
        self.assertEqual(first, [row[:12] for row in plan])
        self.assertTrue(all(len(row) == 24 for row in plan))
        # Whole-family copies retain every arm/item; an unstratified projection
        # would quietly alter sample size and cannot be used for this protocol.
        with self.assertRaises(ValueError):
            project_plan([families[:12] + families[:12]] * 2, families[:12])

    def test_invalid_strata_and_boolean_config_rejected(self):
        for kwargs in ({'strata': [['a', 'a']]}, {'strata': [['a']]},
                       {'seed': True}, {'resamples': True}, {'resamples': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                bootstrap_plan(['a', 'b'], **kwargs)

    def test_analytic_radii_and_clipped_endpoint_bounds(self):
        self.assertAlmostEqual(hoeffding(Fraction(1, 2), 6)['radius'], .5544426220774891)
        result = hoeffding(0, 24, bounds=(-1, 1), alpha=Fraction(1, 40))
        self.assertAlmostEqual(result['radius'], .604292053747874)
        self.assertAlmostEqual(hoeffding(0, 12, bounds=(-1, 1))['radius'], .7841002756996854)
        self.assertEqual(hoeffding(0, 6)['lower'], 0)
        self.assertEqual(hoeffding(1, 6)['upper'], 1)
        for kwargs in ({'families': True}, {'families': 0}, {'families': 65},
                       {'families': 6, 'alpha': 0}, {'families': 6, 'bounds': [1, 0]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                hoeffding(0, **kwargs)

    def test_equal_family_weights_joint_bootstrap_and_leave_one_out(self):
        rows = [{'unit': 'a1', 'family': 'a', 'values': {'B': 0, 'C': 1}},
                {'unit': 'a2', 'family': 'a', 'values': {'B': 1, 'C': 1}},
                {'unit': 'b1', 'family': 'b', 'values': {'B': 1, 'C': 0}}]
        result = family_summary(rows, ['B', 'C'], plan=[['a', 'a'], ['b', 'b']])
        difference = result['contrasts'][0]
        self.assertEqual(difference['estimate_exact'], '-1/4')
        self.assertEqual(difference['family_values_exact'], {'a': '1/2', 'b': '-1'})
        self.assertEqual(difference['bootstrap']['lower_exact'], '-1')
        self.assertEqual(difference['bootstrap']['upper_exact'], '1/2')
        self.assertEqual(difference['leave_one_family_out'],
                         {'minimum_exact': '-1', 'maximum_exact': '1/2'})

    def test_bootstrap_quantile_indices_and_unknown_operational_rows(self):
        rows = [{'unit': 'a', 'family': 'a', 'values': {'B': 0, 'C': 1}}]
        result = family_summary(rows, ['B', 'C'], plan=[['a']] * 4000)
        band = result['contrasts'][0]['bootstrap']
        self.assertEqual((band['lower_index'], band['upper_index']), (99, 3900))
        self.assertEqual(result['contrasts'][0]['leave_one_family_out']['minimum_exact'], None)
        rows[0]['values']['C'] = None
        with self.assertRaises(ValueError):
            family_summary(rows, ['B', 'C'], plan=[['a']] * 2)

    def test_primary_positive_direction_only_two_holm_tests(self):
        result = promotion(primary(), completions={'baseline': 48, 'sham': 48, 'candidate': 48}, latency_us=costs())
        self.assertEqual(result['decision'], 'PROMOTE')
        self.assertEqual({r['id'] for r in result['holm']['results']},
                         {'candidate-minus-baseline', 'candidate-minus-sham'})
        self.assertTrue(all(r['p_exact'] == '1/16777216' for r in result['holm']['results']))
        self.assertTrue(all(r['adjusted_p_exact'] == '1/8388608' for r in result['holm']['results']))

    def test_adverse_and_tied_candidates_cannot_pass_inclusive_positive_tail(self):
        for candidate in (0,):
            rows = primary()
            for row in rows:
                row['values'].update(candidate=candidate, baseline=1, sham=1)
            result = promotion(rows, completions=dict.fromkeys(costs(), 48), latency_us=costs())
            self.assertEqual(result['decision'], 'REJECT')
            self.assertTrue(all(r['p_exact'] == '1' for r in result['holm']['results']))
        rows = primary()
        for row in rows:
            row['values'] = dict.fromkeys(costs(), 0)
        tied = promotion(rows, completions=dict.fromkeys(costs(), 48), latency_us=costs())
        self.assertFalse(tied['uncertainty_pass'])
        self.assertTrue(all(r['p_exact'] == '1' for r in tied['holm']['results']))

    def test_observed_gain_integer_boundary_does_not_override_uncertainty(self):
        for extra, expected in ((4, False), (5, True)):
            rows = primary()
            for i, row in enumerate(rows):
                row['values']['candidate'] = int(i < extra)
            result = promotion(rows, completions=dict.fromkeys(costs(), 48), latency_us=costs())
            self.assertEqual(result['minimum_observed_gain_pass'], {'baseline': expected, 'sham': expected})
            self.assertEqual(result['decision'], 'REJECT')

    def test_completion_two_failure_boundary_is_separate_from_credit(self):
        for completed, expected in ((46, True), (45, False)):
            result = promotion(primary(), completions={'baseline': 48, 'sham': 48, 'candidate': completed}, latency_us=costs())
            self.assertEqual(result['completion_pass'], expected)

    def test_even_median_boundary_and_microsecond_epsilon(self):
        latencies = costs()
        latencies['baseline'] = [1] * 23 + [100, 102] + [1000] * 23
        latencies['candidate'] = [1] * 23 + [126, 126] + [2000] * 23
        result = promotion(primary(), completions=dict.fromkeys(costs(), 48), latency_us=latencies)
        self.assertEqual(result['median_latency_us_exact']['baseline'], '101')
        self.assertEqual(result['candidate_baseline_median_ratio_exact'], '126/101')
        self.assertTrue(result['cost_pass'])
        # 126.5 /101 exceeds1.25: exact medians, not rounded seconds or median ratios.
        latencies['candidate'][24] = 127
        result = promotion(primary(), completions=dict.fromkeys(costs(), 48), latency_us=latencies)
        self.assertFalse(result['cost_pass'])
        latencies = costs(); latencies['candidate'] = [125] * 48
        self.assertTrue(promotion(primary(), completions=dict.fromkeys(costs(), 48), latency_us=latencies)['cost_pass'])
        latencies['candidate'][24:] = [126] * 24
        self.assertFalse(promotion(primary(), completions=dict.fromkeys(costs(), 48), latency_us=latencies)['cost_pass'])

    def test_missing_invalid_or_zero_baseline_cost_never_dropped(self):
        for arm, value in (('baseline', None), ('candidate', None), ('sham', None), ('candidate', -1)):
            latencies = costs(); latencies[arm][0] = value
            result = promotion(primary(), completions=dict.fromkeys(costs(), 48), latency_us=latencies)
            self.assertFalse(result['cost_resolved'])
            self.assertFalse(result['cost_pass'])
            self.assertEqual(result['decision'], 'REJECT')
            self.assertIsNone(result['candidate_baseline_median_ratio_exact'])
        latencies = costs(); latencies['baseline'] = [0] * 48
        self.assertFalse(promotion(primary(), completions=dict.fromkeys(costs(), 48), latency_us=latencies)['cost_resolved'])

    def test_incomplete_unequal_duplicate_and_nonbinary_primary_rejected(self):
        bad = [primary()[:-1], primary() + [primary()[0]], deepcopy(primary())]
        bad[-1][0]['family'] = 'other'
        for rows in bad:
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                promotion(rows, completions=dict.fromkeys(costs(), 48), latency_us=costs())
        for value in (True, .5, None):
            rows = primary(); rows[0]['values']['candidate'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                promotion(rows, completions=dict.fromkeys(costs(), 48), latency_us=costs())
        latencies = costs(); latencies['baseline'].pop()
        with self.assertRaises(ValueError):
            promotion(primary(), completions=dict.fromkeys(costs(), 48), latency_us=latencies)


if __name__ == '__main__':
    unittest.main()

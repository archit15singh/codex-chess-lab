import copy
import unittest

from chesslab.study_analysis import ARMS, CONTRASTS, static_contrasts


def row(unit, family, **values):
    return {'unit': unit, 'family': family,
            'values': {arm: values.get(arm, 0) for arm in ARMS}}


class StudyAnalysisTests(unittest.TestCase):
    def test_directions_and_factorial_interaction(self):
        rows = [row('a', 'f1', A=0, B=1, C=2, D=6, E=8, F=3, G=10, H=4, I=1)]
        result = static_contrasts(rows, resamples=10)
        effects = {name: value['contrasts'][0]['estimate']
                   for name, value in result['main_pairwise_cohorts'].items()}
        self.assertEqual(effects, {'occupancy': 1, 'legality_image': 2,
            'state_plus_legality': 6, 'legality_with_state': 5, 'state_with_legality': 4,
            'effort_high_minus_low': -2, 'adaptive_minus_high': -3,
            'adaptive_minus_low': -5, 'bounded_search': 4, 'reflection': 4,
            'lesson_content': 3, 'sham_context': 1})
        self.assertEqual(result['factorial_interaction']['contrasts'][0]['estimate'], 3)

    def test_partial_pair_vs_all_arm_coverage(self):
        rows = [row('a', 'f1', A=1, B=2, G=None), row('b', 'f2', A=2, B=6)]
        result = static_contrasts(rows, resamples=10)
        main = result['main_pairwise_cohorts']['occupancy']
        common = result['all_arm_complete_sensitivity']['occupancy']
        self.assertEqual(main['common_units'], 2)
        self.assertEqual(main['contrasts'][0]['estimate'], 2.5)
        self.assertEqual(common['common_units'], 1)
        self.assertEqual(common['contrasts'][0]['estimate'], 4)
        self.assertEqual(result['coverage']['available_units_by_arm']['G'], 1)

    def test_missing_component_excludes_interaction_but_not_other_pairs(self):
        result = static_contrasts([row('a', 'f1', A=0, B=1, C=None, D=5)], resamples=5)
        self.assertEqual(result['main_pairwise_cohorts']['occupancy']['common_units'], 1)
        self.assertEqual(result['factorial_interaction']['common_units'], 0)
        self.assertIsNone(result['factorial_interaction']['contrasts'][0]['estimate'])

    def test_family_weighting_failure_zero_and_negative_values_retained(self):
        rows = [row('a', 'large', H=-2), row('b', 'large', H=-2), row('c', 'small', H=0)]
        result = static_contrasts(rows, resamples=10)
        effect = result['main_pairwise_cohorts']['reflection']['contrasts'][0]
        self.assertEqual(effect['estimate'], -1)
        self.assertEqual(effect['family_differences'], {'large': -2, 'small': 0})
        self.assertEqual(result, static_contrasts(rows, resamples=10))

    def test_complete_matrix_validation_precedes_projection(self):
        rows = [row('a', 'f1')]
        for arm in ARMS:
            bad = copy.deepcopy(rows)
            del bad[0]['values'][arm]
            with self.assertRaises(ValueError):
                static_contrasts(bad, resamples=1)
        bad = copy.deepcopy(rows)
        bad[0]['values']['G'] = float('nan')
        with self.assertRaises(ValueError):
            static_contrasts(bad, resamples=1)
        self.assertEqual(len(CONTRASTS), 12)

    def test_schedule_reconciliation_rejects_missing_units_and_wrong_family(self):
        rows = [row('a', 'f1'), row('b', 'f2')]
        schedule = [{'trial_id': f'{r["unit"]}-{a}', 'item_id': r['unit'],
                     'family_id': r['family'], 'arm': a} for r in rows for a in ARMS]
        self.assertTrue(static_contrasts(rows, schedule=schedule, resamples=1)['assignment_reconciled'])
        for bad in [rows[:1], [row('a', 'f1'), row('b', 'wrong')]]:
            with self.assertRaisesRegex(ValueError, 'frozen assignment'):
                static_contrasts(bad, schedule=schedule, resamples=1)

    def test_schedule_duplicate_and_missing_treatment_rejected(self):
        rows = [row('a', 'f1')]
        schedule = [{'trial_id': a, 'item_id': 'a', 'family_id': 'f1', 'arm': a} for a in ARMS]
        for bad in [schedule[:-1], schedule + schedule[:1]]:
            with self.assertRaises(ValueError):
                static_contrasts(rows, schedule=bad, resamples=1)


if __name__ == '__main__':
    unittest.main()

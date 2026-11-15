import copy
import unittest

from chesslab.metrics import game_metrics


def fixtures():
    config = {'condition': 'unaided', 'capabilities': ['screenshot', 'coordinate_click'],
              'model': 'test', 'reasoning': 'high', 'seed': 1, 'purpose': 'pilot', 'permission': 'fixture'}
    events = [
        {'kind': 'intent', 'created': '2026-01-01T00:00:05Z',
         'payload': {'action_id': '1', 'move': 'e2e4', 'decision_observed_at': '2026-01-01T00:00:00Z'}},
        {'kind': 'verification', 'created': '2026-01-01T00:00:06Z',
         'payload': {'action_id': '1', 'outcome': 'uncertain'}},
        {'kind': 'verification', 'created': '2026-01-01T00:00:08Z',
         'payload': {'action_id': '1', 'outcome': 'executed'}},
        {'kind': 'intent', 'created': '2026-01-01T00:00:12Z',
         'payload': {'action_id': '2', 'move': 'd2d5'}},
        {'kind': 'verification', 'created': '2026-01-01T00:00:14Z',
         'payload': {'action_id': '2', 'outcome': 'not_executed'}},
        {'kind': 'intent', 'created': '2026-01-01T00:00:18Z',
         'payload': {'action_id': '3', 'move': 'd2d4'}},
        {'kind': 'observation', 'created': '2026-01-01T00:00:20Z',
         'payload': {'record_type': 'harness_stop', 'pending_action_id': '3'}}]
    score = lambda cp: {'cp': cp, 'mate': None, 'lowerbound': False, 'upperbound': False}
    evaluation = {'engine_analysis': {'rows': [
        {'turn': 'white', 'move': 'e2e4', 'best': score(100), 'selected': score(-100), 'cp_loss_raw': 200},
        {'turn': 'black', 'move': 'e7e5', 'best': score(0), 'selected': score(0), 'cp_loss_raw': 0}]}}
    return {'run': 'fixture', 'config': config, 'events': events}, evaluation


class MetricsTests(unittest.TestCase):
    def test_attempts_are_not_double_counted_or_scored_as_executed(self):
        run, evaluation = fixtures()
        result = game_metrics(run, evaluation, actor='white')
        self.assertEqual(result['attempted'], 3)
        self.assertEqual(result['latest_verification_counts'],
                         {'executed': 1, 'not_executed': 1, 'unverified': 1})
        self.assertEqual(result['unresolved'], 1)
        self.assertEqual(result['endpoint']['completed'], 0)
        self.assertEqual(result['quality']['threshold_counts'], {'100': 1, '200': 1, '300': 0})
        self.assertEqual(result['timing']['decision_image_to_intent']['missing'], 2)
        self.assertEqual(result['timing']['intent_to_conclusive_verification']['mean_seconds'], 2.5)

    def test_wrong_actor_or_sequence_rejected(self):
        run, evaluation = fixtures()
        with self.assertRaisesRegex(ValueError, 'move sequence differs'):
            game_metrics(run, evaluation, actor='black')
        evaluation['engine_analysis']['rows'][0]['move'] = 'd2d4'
        with self.assertRaisesRegex(ValueError, 'move sequence differs'):
            game_metrics(run, evaluation, actor='white')

    def test_legacy_bound_metadata_is_not_assumed_false(self):
        run, evaluation = fixtures()
        for score in (evaluation['engine_analysis']['rows'][0]['best'],
                      evaluation['engine_analysis']['rows'][0]['selected']):
            del score['lowerbound']
            del score['upperbound']
        quality = game_metrics(run, evaluation, actor='white')['quality']
        self.assertEqual(quality['cp_comparable'], 0)
        self.assertEqual(quality['cp_unavailable'], {'missing_bound_metadata': 1})
        self.assertEqual(quality['finite_search_inversions'], 0)
        self.assertEqual(quality['threshold_counts'], {'100': 0, '200': 0, '300': 0})

    def test_mate_bounds_and_inversions_remain_distinct(self):
        run, evaluation = fixtures()
        row = evaluation['engine_analysis']['rows'][0]
        for field, value, category in [('mate', 2, 'mate_score'), ('lowerbound', True, 'bounded_score'),
                                       ('cp', None, 'missing_score')]:
            variant = copy.deepcopy(evaluation)
            variant['engine_analysis']['rows'][0]['best'][field] = value
            result = game_metrics(run, variant, actor='white')['quality']
            self.assertEqual(result['cp_comparable'], 0)
            self.assertEqual(result['cp_unavailable'], {category: 1})
            self.assertIsNone(result['mean_raw_cp_difference'])
        row['selected']['cp'] = 150
        row['cp_loss_raw'] = -50
        quality = game_metrics(run, evaluation, actor='white')['quality']
        self.assertEqual(quality['mean_raw_cp_difference'], -50)
        self.assertEqual(quality['mean_nonnegative_cp_difference'], 0)
        self.assertEqual(quality['finite_search_inversions'], 1)

    def test_corrupt_outcomes_timing_and_scores_rejected(self):
        run, evaluation = fixtures()
        run['events'][2]['created'] = '2025-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'negative timing'):
            game_metrics(run, evaluation, actor='white')
        run, evaluation = fixtures()
        evaluation['engine_analysis']['rows'][0]['cp_loss_raw'] = 0
        with self.assertRaisesRegex(ValueError, 'score difference'):
            game_metrics(run, evaluation, actor='white')
        run, evaluation = fixtures()
        run['events'].insert(3, copy.deepcopy(run['events'][2]))
        with self.assertRaisesRegex(ValueError, 'conclusive resolution'):
            game_metrics(run, evaluation, actor='white')


if __name__ == '__main__':
    unittest.main()

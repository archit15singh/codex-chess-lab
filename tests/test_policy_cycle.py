import copy
import json
from pathlib import Path
import tempfile
import unittest

from chesslab.policy_cycle import choose, digest, seal, select, validate_plan


def fixture():
    return {'cycle_id': 'synthetic', 'protocol_sha256': 'a' * 64,
            'final_manifest_sha256': 'b' * 64, 'training_families': ['train'],
            'final_families': ['test'],
            'development_units': [{'unit': u, 'family': f}
                                  for u, f in [('x1', 'x'), ('x2', 'x'), ('y1', 'y')]],
            'training_findings': [{'family': 'train', 'category': 'interaction',
                                   'evidence_sha256': 'c' * 64}],
            'baseline': {'id': 'baseline', 'prompt': 'base'},
            'sham': {'id': 'sham', 'prompt': 'sham'},
            'candidates': [{'id': c, 'prompt': 'policy ' + c, 'mechanism': 'one mechanism',
                            'training_finding_indices': [0]} for c in ['c1', 'c2', 'c3']]}


def observations(plan):
    return [{'unit': u['unit'], 'arm': p['id'], 'received': True, 'on_time': True,
             'format_valid': True, 'legal': True, 'reference_available': True,
             'best_agreement': False, 'source_sha256': 'd' * 64}
            for u in plan['development_units'] for p in validate_plan(plan)]


class PolicyCycleTests(unittest.TestCase):
    def test_family_weighting_differs_from_pooled_success_and_exact_tie_order(self):
        plan = fixture()
        rows = observations(plan)
        for r in rows:
            r['best_agreement'] = ((r['arm'] == 'c1' and r['unit'] in ('x1', 'x2'))
                                  or (r['arm'] in ('c2', 'c3') and r['unit'] == 'y1'))
        result = choose(plan, rows)
        self.assertEqual(result['scores_exact'], {'baseline': '0', 'sham': '0',
                                                  'c1': '1/2', 'c2': '1/2', 'c3': '1/2'})
        self.assertEqual(result['selected_id'], 'c1')
        # Same pooled score, different family weighting: c2 beats c1 now.
        next(r for r in rows if r['arm'] == 'c1' and r['unit'] == 'x2')['best_agreement'] = False
        self.assertEqual(choose(plan, rows)['selected_id'], 'c2')
        self.assertEqual(choose(plan, rows)['scores_exact']['c1'], '1/4')

    def test_failed_and_late_answers_are_zero_and_cannot_be_dropped(self):
        plan = fixture()
        rows = observations(plan)
        for row in rows:
            row['best_agreement'] = True
        late = next(r for r in rows if r['arm'] == 'c1' and r['unit'] == 'y1')
        late['on_time'] = False
        missing = next(r for r in rows if r['arm'] == 'c2' and r['unit'] == 'y1')
        missing.update(received=False, on_time=False, format_valid=False,
                       legal=False, best_agreement=None)
        result = choose(plan, rows)
        self.assertEqual(result['selected_id'], 'c3')
        self.assertEqual(result['scores_exact']['c1'], '1/2')
        self.assertEqual(result['scores_exact']['c2'], '1/2')
        with self.assertRaisesRegex(ValueError, 'every assigned'):
            choose(plan, rows[:-1])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            choose(plan, rows + rows[:1])

    def test_missing_reference_shared_across_arms_and_inconsistent_flags_rejected(self):
        plan = fixture()
        rows = observations(plan)
        rows[0].update(reference_available=False, best_agreement=None)
        with self.assertRaisesRegex(ValueError, 'common reference'):
            choose(plan, rows)
        for row in rows:
            if row['unit'] == 'x1':
                row.update(reference_available=False, best_agreement=None)
        self.assertEqual(choose(plan, rows)['selected_id'], 'c1')
        rows[0]['best_agreement'] = False
        with self.assertRaisesRegex(ValueError, 'agreement must be unknown'):
            choose(plan, rows)
        rows = observations(plan)
        rows[0]['received'] = False
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            choose(plan, rows)

    def test_invalid_splits_candidates_and_unassigned_rows(self):
        for mutate in [lambda p: p['final_families'].append('train'),
                       lambda p: p['candidates'].append(p['candidates'][0]),
                       lambda p: p['candidates'][0].update(training_finding_indices=[True]),
                       lambda p: p['candidates'][0].update(id='baseline'),
                       lambda p: p['candidates'][0].update(prompt='base'),
                       lambda p: p['training_findings'][0].update(family='test')]:
            plan = fixture()
            mutate(plan)
            with self.assertRaises(ValueError):
                validate_plan(plan)
        rows = observations(fixture())
        rows[0]['unit'] = 'final-item'
        with self.assertRaisesRegex(ValueError, 'unassigned'):
            choose(fixture(), rows)

    def test_seal_select_once_source_binding_and_self_contained_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / 'plan.json'
            dev_path = Path(directory) / 'development.json'
            plan = fixture()
            plan_hash = seal(plan_path, plan)
            self.assertEqual(plan_hash, digest(plan_path.read_bytes()))
            with self.assertRaises(FileExistsError):
                seal(plan_path, plan)
            dev = {'phase': 'development', 'plan_sha256': plan_hash,
                   'observations': observations(plan)}
            dev_path.write_text(json.dumps(dev))
            output_hash = select(plan_path, dev_path)
            output = Path(str(plan_path) + '.selection.json')
            self.assertEqual(output_hash, digest(output.read_bytes()))
            result = json.loads(output.read_bytes())
            self.assertEqual(result['sealed_plan']['plan'], plan)
            self.assertEqual(result['development'], dev)
            self.assertEqual(result['selection']['selected_id'], 'c1')
            self.assertEqual(result['selection']['selected_prompt_sha256'], digest(b'policy c1'))
            with self.assertRaises(FileExistsError):
                select(plan_path, dev_path)
            for field, value in [('phase', 'final'), ('plan_sha256', '0' * 64)]:
                bad = copy.deepcopy(dev)
                bad[field] = value
                dev_path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    select(plan_path, dev_path)


if __name__ == '__main__':
    unittest.main()

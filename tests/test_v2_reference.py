"""Synthetic UCI process fixtures, never Stockfish or model performance."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import chess

from chesslab import engine_work
from chesslab.v2_reference import analyze


FAKE = r'''
import sys,time
mode = MODE
black = False
for line in sys.stdin:
 line=line.strip()
 if line == 'uci':
  if mode == 'hang_init': time.sleep(60)
  print('id name Stockfish Synthetic engineering fixture')
  print('option name Threads type spin default 1 min 1 max 16')
  print('option name Hash type spin default 16 min 1 max 64')
  print('option name Skill Level type spin default 20 min 0 max 20')
  print('option name UCI_LimitStrength type check default false')
  print('option name SyzygyPath type string default <empty>')
  print('option name Clear Hash type button')
  print('uciok',flush=True)
 elif line == 'isready': print('readyok',flush=True)
 elif line.startswith('position '):black=' b ' in line
 elif line.startswith('go '):
  if mode == 'hang_search': time.sleep(60)
  words=line.split();selected=words[words.index('searchmoves')+1] if 'searchmoves' in words else None
  move=selected or ('e7e5' if black else 'e2e4');cp=10 if selected else 20
  if mode=='inversion':cp=30 if selected else 20
  if mode=='wrong_root':move='e7e5' if black else 'e2e4'
  score='mate 3' if mode=='mate' and not selected else 'cp '+str(cp)
  if mode=='bound' and not selected:score+=' lowerbound'
  print('info depth 4 score '+score+' nodes 101 time 1 pv '+move)
  print('bestmove '+move,flush=True)
 elif line=='quit':break
'''


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.budget = self.root / 'engine.sqlite'
        engine_work.create(self.budget, 200, provenance={'purpose': 'synthetic fixtures only'})
        self.counter = 0

    def run_reference(self, mode='normal', selected='d2d4', **changes):
        self.counter += 1
        engine = self.root / f'fake-{self.counter}'
        engine.write_text('#!' + sys.executable + '\n' + FAKE.replace('MODE', repr(mode)))
        engine.chmod(0o700)
        request = self.root / f'request-{self.counter}.json'
        request.write_text(json.dumps({'engine': str(engine), 'fen': chess.STARTING_FEN,
            'nodes': 100, 'timeout_seconds': 1, 'selected_move': selected, **changes}))
        output = self.root / f'output-{self.counter}'
        return request, output

    def invoke(self, request, output):
        return analyze(request, output, budget=self.budget, identity=output.name)

    def test_two_root_searches_snapshot_scores_nodes_and_proven_exit(self):
        request, output = self.run_reference()
        result = self.invoke(request, output)
        self.assertEqual(result['status'], 'analyzed')
        self.assertTrue(result['process_stopped'])
        self.assertEqual(result['process_returncode'], 0)
        self.assertEqual(result['best_move'], 'e2e4')
        self.assertFalse(result['best_move_agreement'])
        self.assertEqual(result['cp_loss_raw'], 10)
        self.assertFalse(result['finite_search_inversion'])
        self.assertEqual([r['nodes'] for r in result['analyses']], [101, 101])
        self.assertEqual([r['root_move'] for r in result['analyses']], [None, 'd2d4'])
        state = engine_work.summary(self.budget)
        self.assertEqual(state['charged_ns'], result['active_ns'])
        self.assertEqual(state['operations'][0]['status'], 'measured')
        self.assertTrue(all(result[k] for k in ['request_unchanged', 'sources_unchanged', 'engine_binary_unchanged']))
        with self.assertRaises(FileExistsError): self.invoke(request, output)
        self.assertEqual(len(engine_work.summary(self.budget)['operations']), 1)

    def test_single_search_assistance_returns_no_invented_selected_score(self):
        request, output = self.run_reference(selected=None)
        result = self.invoke(request, output)
        self.assertEqual(len(result['analyses']), 1)
        self.assertEqual(result['best_move'], 'e2e4')
        self.assertNotIn('cp_loss_raw', result)

    def test_scores_use_side_to_move_for_black_too(self):
        board = chess.Board()
        board.push_uci('e2e4')
        request, output = self.run_reference(selected='d7d5', fen=board.fen())
        result = self.invoke(request, output)
        self.assertEqual(result['best_move'], 'e7e5')
        self.assertEqual([s['cp'] for s in result['analyses']], [20, 10])
        self.assertEqual(result['cp_loss_raw'], 10)

    def test_mate_bounds_and_inversions_remain_explicit(self):
        for mode in ['mate', 'bound', 'inversion']:
            with self.subTest(mode=mode):
                request, output = self.run_reference(mode)
                result = self.invoke(request, output)
                if mode == 'inversion':
                    self.assertEqual(result['cp_loss_raw'], -10)
                    self.assertTrue(result['finite_search_inversion'])
                else:
                    self.assertFalse(result['cp_comparable'])
                    self.assertIsNone(result['cp_loss_raw'])
                    self.assertIsNone(result['finite_search_inversion'])
                    if mode == 'mate': self.assertEqual(result['analyses'][0]['mate'], 3)
                    if mode == 'bound': self.assertTrue(result['analyses'][0]['lowerbound'])

    def test_hung_initialization_and_search_are_killed_and_accounted(self):
        for mode in ['hang_init', 'hang_search']:
            with self.subTest(mode=mode):
                request, output = self.run_reference(mode)
                with self.assertRaisesRegex(RuntimeError, 'operation failed'): self.invoke(request, output)
                result = json.loads((output / 'result.json').read_bytes())
                self.assertEqual(result['status'], 'failed')
                self.assertTrue(result['process_stopped'])
                self.assertIsInstance(result['process_returncode'], int)
                self.assertEqual(result['error_type'], 'TimeoutError')
                self.assertLess(result['active_ns'], 10_000_000_000)
        self.assertTrue(all(r['status'] == 'measured' for r in engine_work.summary(self.budget)['operations']))

    def test_engine_ignoring_selected_root_is_preserved_as_failure(self):
        request, output = self.run_reference('wrong_root')
        with self.assertRaisesRegex(RuntimeError, 'operation failed'): self.invoke(request, output)
        result = json.loads((output / 'result.json').read_bytes())
        self.assertEqual(result['error_type'], 'ValueError')
        self.assertEqual(len(result['analyses']), 2)
        self.assertTrue(result['process_stopped'])

    def test_unconfirmed_process_exit_cannot_refund_allowance(self):
        request, output = self.run_reference(selected=None)
        unknown = {'status': 'exit_unconfirmed', 'process_stopped': False,
                   'process_returncode': None, 'analyses': []}
        with patch('chesslab.v2_reference._operate', new=AsyncMock(return_value=unknown)):
            with self.assertRaisesRegex(RuntimeError, 'exit unconfirmed'): self.invoke(request, output)
        state = engine_work.summary(self.budget)
        self.assertEqual(state['charged_ns'], state['operations'][0]['reserved_ns'])
        self.assertEqual(state['operations'][0]['status'], 'full_reservation_retained')
        self.assertFalse(json.loads((output / 'result.json').read_bytes())['process_stopped'])

    def test_invalid_request_starts_no_process_or_reservation(self):
        for changes in [{'nodes': 0}, {'nodes': True}, {'timeout_seconds': 0},
                        {'selected_move': 'e2e5'}, {'fen': '7k/5K2/6Q1/8/8/8/8/8 b - - 0 1'}]:
            with self.subTest(changes=changes):
                request, output = self.run_reference(**changes)
                with self.assertRaises(ValueError): self.invoke(request, output)
                self.assertFalse(output.exists())
        self.assertEqual(engine_work.summary(self.budget)['operations'], [])


if __name__ == '__main__':
    unittest.main()

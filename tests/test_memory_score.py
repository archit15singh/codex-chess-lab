from datetime import timedelta
import json
from pathlib import Path
import unittest
from unittest.mock import patch

try:
    import chess
    from chesslab import memory_score as score
    from chesslab.corpus import common_rules
except ImportError:
    chess = None

import test_memory_trial as fixtures
from test_memory_trial import dump, response, seal
from chesslab import memory_trial as m


@unittest.skipUnless(chess, 'isolated chess evaluator dependency required')
class MemoryScoreTests(unittest.TestCase):
    setUp = fixtures.MemoryTrialTests.setUp
    prepare = fixtures.MemoryTrialTests.prepare
    submit = fixtures.MemoryTrialTests.submit

    def prepare_source(self, condition='internal'):
        seqpath = self.corpus / 'player/sequences.json'
        source = json.loads(seqpath.read_text())
        seq = source['sequences'][0]
        board, frames = chess.Board(), []
        moves = ['g1f3', 'g8f6', 'f3g1', 'f6g8'] * 6
        self.boards = [board.copy()]
        for ply in range(25):
            if ply:
                board.push_uci(moves[ply - 1])
                self.boards.append(board.copy())
            frames.append({'ply': ply, 'fen': board.fen(), 'rules': common_rules(board),
                           'image': seq['frames'][ply]['image']})
        seq['initial_rules'] = common_rules(chess.Board())
        dump(seqpath, source)
        dump(self.corpus / 'evaluator/families.json', {'families': [
            {'family_id': 'synthetic', 'split': 'final', 'moves_uci': moves, 'frames': frames}]})
        seal(self.corpus)
        self.prepare(condition)
        self.proof = self.root / 'controller-completed.json'
        self.proof.write_text('{"host_status":"completed","synthetic":true}')

    def answer(self, stage):
        ply = [6, 12, 18, 24][stage - 1]
        previous = [0, 6, 12, 18][stage - 1]
        board = self.boards[ply]
        r = response()
        r.update({k: v for k, v in common_rules(board).items() if k != 'halfmove_clock'})
        r['piece_map'] = {s: board.piece_at(chess.parse_square(s)).symbol()
                          if board.piece_at(chess.parse_square(s)) else '.' for s in r['piece_map']}
        r['last_move_uci'] = board.peek().uci()
        r['recall'] = {s: self.boards[previous].piece_at(chess.parse_square(s)).symbol()
                       if self.boards[previous].piece_at(chess.parse_square(s)) else '.' for s in ('d4', 'e5')}
        return r

    def scored(self, suffix='score'):
        return score.score_sequence(self.directory, self.root / suffix, actor_completed=True,
                                    completion_evidence=self.proof)

    def test_complete_sequence_exact_and_wrong_recall_scored_separately(self):
        self.prepare_source('record')
        for stage in range(1, 5):
            m.open_next(self.directory)
            self.time += timedelta(seconds=1)
            value = self.answer(stage)
            if stage == 2:
                value['last_move_uci'] = None
                value['recall']['d4'] = '?'
            self.submit(stage, value)
        self.assertEqual(m.open_next(self.directory)['status'], 'completed')
        result = self.scored()
        self.assertTrue(result['primary_final_exact_board'])
        self.assertEqual(result['checkpoint_denominator'], 4)
        self.assertEqual(result['on_time_exact_boards'], 4)
        second = result['checkpoints'][1]
        self.assertTrue(second['last_move_unknown'])
        self.assertEqual(second['recall_correct_squares'], 1)
        self.assertEqual(second['recall_unknown_squares'], 1)

    def test_late_and_missing_count_in_denominator(self):
        self.prepare_source()
        m.open_next(self.directory)
        self.time += timedelta(seconds=60)
        self.submit(1, self.answer(1))
        result = self.scored()
        self.assertFalse(result['primary_final_exact_board'])
        self.assertEqual(result['checkpoint_denominator'], 4)
        self.assertEqual(result['present_responses'], 1)
        self.assertEqual(result['on_time_exact_boards'], 0)
        self.assertEqual(result['checkpoints'][0]['status'], 'late')
        self.assertEqual(result['checkpoints'][1]['status'], 'not_opened')

    def test_unknowns_and_malformed_are_visible(self):
        self.prepare_source()
        m.open_next(self.directory)
        unknown = response()
        unknown['piece_map'] = {square: '?' for square in unknown['piece_map']}
        self.submit(1, unknown)
        m.open_next(self.directory)
        self.submit(2, raw=b'\xffinvalid')
        result = self.scored()
        row = result['checkpoints'][0]
        self.assertEqual(row['transcription']['unknown_squares'], 64)
        self.assertEqual(row['castling_unknown_flags'], 4)
        self.assertTrue(row['en_passant_unknown'])
        self.assertTrue(row['side_to_move_unknown'])
        self.assertEqual(result['checkpoints'][1]['status'], 'malformed')
        self.assertEqual(result['present_responses'], 2)
        self.assertFalse(result['primary_final_exact_board'])

    def test_authoritative_gate_and_delivery_tampering(self):
        self.prepare_source()
        with self.assertRaisesRegex(ValueError, 'authoritative'):
            score.score_sequence(self.directory, self.root / 'no', actor_completed=False,
                                 completion_evidence=self.proof)
        m.open_next(self.directory)
        self.submit(1, self.answer(1))
        path = m.stage_path(self.directory, 1) / 'open.json'
        opened = json.loads(path.read_text())
        opened['own_prior_responses'] = []
        dump(path, opened)
        with self.assertRaisesRegex(ValueError, 'information channel'):
            self.scored()

    def test_first_hash_read_failure_preserves_reserved_attempt_without_engine(self):
        self.prepare_source()
        failed_output = self.root / 'hash-failure'
        with patch.object(Path, 'read_bytes', side_effect=PermissionError('synthetic hash read denied')):
            with patch('subprocess.Popen') as process:
                with self.assertRaisesRegex(PermissionError, 'hash read denied'):
                    score.score_sequence(self.directory, failed_output, actor_completed=True,
                                         completion_evidence=self.proof)
                process.assert_not_called()
        failure = json.loads((failed_output / 'failure.json').read_text())
        self.assertEqual(failure['error_type'], 'PermissionError')
        self.assertEqual(failure['checkpoint_denominator'], 4)
        self.assertFalse(failure['integrity_valid'])
        self.assertFalse(failure['primary_final_exact_board'])
        self.assertEqual({p.name for p in failed_output.iterdir()}, {'failure.json'})
        with self.assertRaises(FileExistsError):
            score.score_sequence(self.directory, failed_output, actor_completed=True,
                                 completion_evidence=self.proof)

    def test_nested_output_is_rejected_before_creation_even_through_symlink(self):
        self.prepare_source()
        original = set(self.directory.rglob('*'))
        alias = self.root / 'trial-alias'
        alias.symlink_to(self.directory, target_is_directory=True)
        for output in (self.directory / 'score-001', alias / 'score-002'):
            with self.assertRaisesRegex(ValueError, 'disjoint directory trees'):
                score.score_sequence(self.directory, output, actor_completed=True,
                                     completion_evidence=self.proof)
            self.assertFalse(output.exists())
            self.assertEqual(set(self.directory.rglob('*')), original)

    def test_source_history_mismatch_is_not_scored(self):
        self.prepare_source()
        path = self.corpus / 'evaluator/families.json'
        data = json.loads(path.read_text())
        data['families'][0]['frames'][1]['fen'] = chess.STARTING_FEN
        dump(path, data)
        # Simulate sealed source with internally inconsistent history before preparation.
        seal(self.corpus)
        other = self.root / 'other'
        m.prepare(self.corpus, 's-test', 'internal', other)
        with self.assertRaisesRegex(ValueError, 'history/frame'):
            score.score_sequence(other, self.root / 'bad-source', actor_completed=True,
                                 completion_evidence=self.proof)


if __name__ == '__main__':
    unittest.main()

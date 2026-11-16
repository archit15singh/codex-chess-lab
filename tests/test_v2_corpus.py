from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import chess
from chesslab import v2_corpus as corpus


def case(**extra):
    return {'id': 'example', 'family': 'family-a', 'split': 'pilot',
            'task': 'perception', 'moves': ['e2e4', 'e7e5', 'g1f3'],
            'orientation': 'white', 'style': 'plain', **extra}


def spec(*cases):
    return {'schema_version': 2, 'cases': list(cases), 'excluded_position_sha256': []}


class DiagnosticCorpusTests(unittest.TestCase):
    def test_rejects_illegal_history_and_legal_injected_proposal(self):
        with self.assertRaisesRegex(ValueError, 'illegal move'):
            corpus.validate(spec(case(moves=['e2e5'])))
        with self.assertRaisesRegex(ValueError, 'actually be illegal'):
            corpus.validate(spec(case(task='correction', proposal='b8c6')))

    def test_excluded_positions_and_cross_split_reuse_rejected(self):
        item = case()
        value = spec(item)
        value['excluded_position_sha256'] = [corpus.position_hash(corpus.history(item['moves'])[-1])]
        with self.assertRaisesRegex(ValueError, 'excluded'):
            corpus.validate(value)
        with self.assertRaisesRegex(ValueError, 'family crosses splits'):
            corpus.validate(spec(item, case(id='other', split='final')))
        with self.assertRaisesRegex(ValueError, 'position crosses'):
            corpus.validate(spec(item, case(id='other', family='family-b', split='final')))

    def test_history_requires_constructive_ambiguity(self):
        item = case(task='history', moves=['g1f3', 'g8f6', 'b1c3', 'b8c6'],
                    alternative_moves=['b1c3', 'b8c6', 'g1f3', 'g8f6'],
                    frames=[1, 2, 4], query_ply=1, query_squares=['b1', 'g1'])
        checked = corpus.validate(spec(item))
        self.assertEqual(checked[0][1][-1].fen(), checked[0][2][-1].fen())
        bad = deepcopy(item);bad['alternative_moves'] = item['moves']
        with self.assertRaisesRegex(ValueError, 'queried past answer'):
            corpus.validate(spec(bad))
        bad = deepcopy(item);bad['query_ply'] = 4
        with self.assertRaisesRegex(ValueError, 'past checkpoint'):
            corpus.validate(spec(bad))

    def test_nonqueried_exposed_training_frame_cannot_become_final_item(self):
        item = case(task='history', split='training',
                    moves=['g1f3', 'g8f6', 'b1c3', 'b8c6'],
                    alternative_moves=['b1c3', 'b8c6', 'g1f3', 'g8f6'],
                    frames=[0, 1, 2, 4], query_ply=1, query_squares=['b1', 'g1'])
        final = case(id='heldout', family='other', split='final', moves=['g1f3', 'g8f6'])
        with self.assertRaisesRegex(ValueError, 'exposed position crosses'):
            corpus.validate(spec(item, final))

    def test_sealed_rendered_package_separates_truth_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'corpus'
            manifest = corpus.build(spec(case(style='angled', orientation='black')), root)
            self.assertEqual(corpus.verify(root), manifest)
            import json
            player = json.loads((root / 'player/example.json').read_text())
            self.assertNotIn('fen', player)
            self.assertNotIn('piece_map', player)
            image = root / player['image']['path']
            self.assertTrue(image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
            image.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                corpus.verify(root)
            with self.assertRaises(FileExistsError):
                corpus.build(spec(case()), root)

    def test_all_render_styles_are_real_deterministic_images(self):
        import pymupdf
        board = corpus.history(['e2e4', 'e7e5'])[-1]
        for style in corpus.STYLES:
            a, svg_a = corpus.render(board, 'white', style)
            b, svg_b = corpus.render(board, 'white', style)
            self.assertEqual((a, svg_a), (b, svg_b))
            pixels = pymupdf.Pixmap(a)
            self.assertEqual(pixels.pixel(10, 10), (23, 34, 30),
                             'board must stay inset rather than overwrite/crop at canvas origin')
            self.assertEqual(pixels.width, {'compact': 512, 'lowres': 256}.get(style, 760))
            scale = pixels.width / 760
            self.assertNotEqual(pixels.pixel(round(600 * scale), round(380 * scale)), (23, 34, 30),
                                'SVG internal viewBox must scale to the declared board extent')

    def test_manifest_verification_rejects_unlisted_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'corpus'
            corpus.build(spec(case()), root)
            (root / 'unlisted.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'inventory changed'):
                corpus.verify(root)


if __name__ == '__main__':
    unittest.main()

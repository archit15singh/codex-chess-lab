import builtins
from html.parser import HTMLParser
import unittest
from unittest.mock import patch

from chesslab.report import build, _comparable_difference


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current = None
        self.cell = None
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == 'tr':
            self.current = []
        elif tag == 'td':
            self.cell = ''

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag == 'td':
            self.current.append(self.cell)
            self.cell = None
        elif tag == 'tr' and self.current:
            self.rows.append(self.current)
            self.current = None


def evaluation(rows):
    return {'plies': len(rows), 'board_terminal': False, 'result_header': '*',
            'board_result': None, 'pgn_sha256': 'synthetic-fixture',
            'engine_analysis': {'engine_id': {'name': 'synthetic reference'}, 'rows': rows}}


def row(ply, best, selected, difference=None, **extra):
    best = {'lowerbound': False, 'upperbound': False, **best}
    selected = {'lowerbound': False, 'upperbound': False, **selected}
    return {'ply': ply, 'turn': 'white' if ply % 2 else 'black', 'san': 'fixture',
            'best': best, 'selected': selected, 'cp_loss_raw': difference,
            'bounded_search_inversion': difference < 0 if difference is not None else None,
            **extra}


class ReportTests(unittest.TestCase):
    def test_legacy_missing_bounds_are_unknown_and_not_plotted(self):
        legacy = row(1, {'cp': 12}, {'cp': 29}, -17)
        for side in ('best', 'selected'):
            del legacy[side]['lowerbound']
            del legacy[side]['upperbound']
        self.assertIsNone(_comparable_difference(legacy))
        reader = TableReader()
        reader.feed(build(evaluation([legacy]), purpose='feasibility', figures=False))
        self.assertIn('bound metadata unavailable', reader.rows[0][3])
        self.assertEqual(reader.rows[0][5], '-17')
        self.assertIn('missing best bound metadata', reader.rows[0][6])
        self.assertEqual(reader.rows[0][7], 'unavailable')

    def test_scores_keep_bounds_mates_missing_and_inversions_distinct(self):
        source = evaluation([
            row(1, {'cp': 12}, {'cp': 29}, -17),
            row(2, {'cp': 55, 'lowerbound': True}, {'cp': 23, 'upperbound': True}),
            row(3, {'mate': 3, 'lowerbound': True}, {'mate': -2, 'upperbound': True}),
            row(4, {}, {'cp': 0}),
        ])
        reader = TableReader()
        reader.feed(build(source, purpose='feasibility', figures=False))
        inversion, bounded, mate, missing = reader.rows
        self.assertEqual(inversion[3:7], ['cp 12 (no bound flag)', 'cp 29 (no bound flag)',
                                         '-17', 'finite-search inversion'])
        self.assertEqual(inversion[7], 'True')
        self.assertEqual(bounded[3:6], ['cp 55 (lowerbound)', 'cp 23 (upperbound)', 'unavailable'])
        self.assertIn('best lowerbound', bounded[6])
        self.assertIn('selected upperbound', bounded[6])
        self.assertEqual(mate[3:6], ['mate 3 (lowerbound)', 'mate -2 (upperbound)', 'unavailable'])
        self.assertIn('best mate score', mate[6])
        self.assertIn('selected mate score', mate[6])
        self.assertEqual(missing[3:6], ['unavailable (no bound flag)', 'cp 0 (no bound flag)',
                                      'unavailable'])
        self.assertEqual(missing[6], 'missing best score')
        self.assertIsNone(source['engine_analysis']['rows'][2]['cp_loss_raw'])

    def test_table_only_mode_does_not_import_plotting_dependencies(self):
        original_import = builtins.__import__

        def reject_plotting(name, *args, **kwargs):
            if name == 'matplotlib' or name.startswith('matplotlib.'):
                raise AssertionError('table-only mode imported matplotlib')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=reject_plotting):
            html = build(evaluation([row(1, {'cp': 1}, {'cp': 0}, 1)]),
                         purpose='pilot', figures=False)
        self.assertIn('Figure omitted', html)
        self.assertNotIn('<svg', html)

    def test_untrusted_text_is_escaped_and_not_executable_markup(self):
        attack = '<script>alert("fixture")</script>'
        source = evaluation([row(1, {'cp': 1}, {'cp': 0}, 1, san=attack)])
        source['engine_analysis']['engine_id']['name'] = '<img src=x onerror=alert(1)>'
        html = build(source, purpose='heldout', figures=False)
        reader = TableReader()
        reader.feed(html)
        self.assertEqual(reader.rows[0][2], attack)
        self.assertNotIn('script', reader.tags)
        self.assertNotIn('img', reader.tags)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('No strength or grandmaster-level estimate', html)
        self.assertIn('not the final research paper', html)

    def test_empty_measurements_and_explicit_purpose(self):
        html = build(evaluation([]), purpose='pilot', figures=False)
        self.assertIn('No engine measurements available', html)
        with self.assertRaisesRegex(ValueError, 'purpose'):
            build(evaluation([]), purpose='synthetic', figures=False)

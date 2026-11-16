"""Pure reporting guards and formatting; no PDF or experimental data creation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts import render_research_html as html
from scripts import render_research_paper as paper

class ReportTests(unittest.TestCase):
    def test_reference_numbers_and_escaping(self):
        body, _ = html.render_markdown('# Example\n\n1. First & second\n2. Next source\n',Path('.'),{})
        self.assertIn('1. First &amp; second',body)
        self.assertIn('2. Next source',body)
        self.assertEqual(paper.inline('A < B'), 'A &lt; B')

    def test_missing_value_distinct_from_zero(self):
        self.assertEqual(html.numeric(None),'Unavailable')
        self.assertEqual(html.numeric(0),'0.00')
        self.assertEqual(html.numeric(.25,100),'25.00')

    def test_manuscript_replacement_rejected_even_with_replace(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);source=root/'paper.md';source.write_text('# Example')
            for replace in [False,True]:
                with self.assertRaises(ValueError):html.render(source,source,root=root,aliases={},contrasts={},title='Example',subtitle='',date='Example',replace_derived=replace)
            self.assertEqual(source.read_text(),'# Example')

    def test_existing_and_symlink_output_preserved(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);source=root/'paper.md';source.write_text('# Example');target=root/'report.html';target.write_text('prior')
            with self.assertRaises(FileExistsError):html.render(source,target,root=root,aliases={},contrasts={},title='Example',subtitle='',date='Example')
            link=root/'link.html';link.symlink_to(target)
            with self.assertRaises(ValueError):html.render(source,link,root=root,aliases={},contrasts={},title='Example',subtitle='',date='Example',replace_derived=True)
            self.assertEqual(target.read_text(),'prior')

    def test_figure_escape_rejected(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);assets=root/'assets';assets.mkdir();(root/'outside.png').write_bytes(b'not an image')
            with self.assertRaises(ValueError):html.render_markdown('![Caption](../outside.png)',assets,{})

    def test_png_dimensions_reserve_layout_before_lazy_load(self):
        import struct
        with TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'figure.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+struct.pack('>II',320,200))
            body,_=html.render_markdown('![Example](figure.png)',root,{})
            self.assertIn('width="320" height="200"',body)
            self.assertIn('loading="lazy"',body)

    def test_print_normalization_and_unknown_glyph_rejection(self):
        self.assertEqual(paper.normalized('low\u2013high \u2264 2'),'low-high <= 2')
        with self.assertRaises(ValueError):paper.normalized('\u2603')

if __name__=='__main__':unittest.main()

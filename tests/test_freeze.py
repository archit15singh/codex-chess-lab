import hashlib
from pathlib import Path
import tempfile
import unittest
from chesslab.freeze import FILES, freeze, verify


class FreezeTests(unittest.TestCase):
    def test_source_changes_do_not_change_frozen_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'mutable'
            for relative in FILES:
                p = source / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'original mechanical source')
            (source / 'chesslab/evaluate.py').write_text('not part of player environment')
            snapshot = Path(tmp) / 'frozen'
            manifest = freeze(source, snapshot)
            (source / FILES[0]).write_bytes(b'checkout changed')
            self.assertEqual(verify(snapshot), manifest)
            self.assertFalse((snapshot / 'chesslab/evaluate.py').exists())
            with self.assertRaises(FileExistsError):
                freeze(source, snapshot)
            for relative in FILES:
                self.assertEqual(hashlib.sha256((snapshot / relative).read_bytes()).hexdigest(),
                                 manifest['files'][relative])
            p = snapshot / FILES[0]
            p.chmod(0o644)
            p.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'changed'):
                verify(snapshot)

    def test_source_escape_fails_before_creating_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            for relative in FILES:
                p = source / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('fixture')
            outside = Path(tmp) / 'outside'
            outside.write_text('outside')
            p = source / FILES[0]
            p.unlink()
            p.symlink_to(outside)
            destination = Path(tmp) / 'snapshot'
            with self.assertRaisesRegex(ValueError, 'escapes'):
                freeze(source, destination)
            self.assertFalse(destination.exists())

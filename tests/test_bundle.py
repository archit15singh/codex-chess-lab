"""Synthetic export fixtures; no experimental evidence or performance samples."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from chesslab import bundle


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class BundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stage = self.root / 'stage'
        self.stage.mkdir()
        (self.stage / 'data').mkdir()
        (self.stage / 'README.md').write_bytes(b'SYNTHETIC reproduction fixture\n')
        (self.stage / 'data/rows.csv').write_bytes(b'id,value\nSYNTHETIC,3\n')
        self.files = {name: digest((self.stage / name).read_bytes()) for name in ['README.md', 'data/rows.csv']}
        self.archive = self.root / 'result.zip'

    def build(self):
        return bundle.build(self.stage, self.files, self.archive)

    def manifest(self, payloads):
        return {'schema_version': 1, 'files': {name: {'sha256': digest(raw), 'bytes': len(raw)}
                                               for name, raw in payloads.items()}}

    def crafted(self, payloads, *, manifest=None, extra=None):
        with ZipFile(self.archive, 'w') as archive:
            for name, raw in payloads.items():
                archive.writestr(name, raw)
            if extra:
                archive.writestr(*extra)
            value = manifest if manifest is not None else self.manifest(payloads)
            archive.writestr(bundle.MANIFEST, value if isinstance(value, bytes) else json.dumps(value))

    def test_explicit_files_only_and_clean_roundtrip(self):
        (self.stage / 'not-for-export.txt').write_text('SYNTHETIC omitted source')
        result = self.build()
        self.assertEqual(result['payload_files'], 2)
        self.assertEqual(result['archive_sha256'], digest(self.archive.read_bytes()))
        checked = bundle.verify(self.archive)
        destination = self.root / 'extracted'
        self.assertEqual(bundle.extract(self.archive, destination), checked)
        self.assertEqual(bundle.verify_tree(destination), checked)
        self.assertEqual(set(checked['files']), set(self.files))
        for name in self.files:
            self.assertEqual((destination / name).read_bytes(), (self.stage / name).read_bytes())
        self.assertFalse((destination / 'not-for-export.txt').exists())

    def test_same_sources_are_deterministic_without_source_mtimes(self):
        first = self.build()
        os.utime(self.stage / 'README.md', (1_000_000_000, 1_000_000_000))
        other = self.root / 'other.zip'
        second = bundle.build(self.stage, dict(reversed(list(self.files.items()))), other)
        self.assertEqual(first['archive_sha256'], second['archive_sha256'])
        self.assertEqual(self.archive.read_bytes(), other.read_bytes())

    def test_no_overwrite_of_archive_or_destination(self):
        self.build()
        original = self.archive.read_bytes()
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(self.archive.read_bytes(), original)
        target = self.root / 'existing'
        target.mkdir()
        (target / 'keep.txt').write_bytes(b'SYNTHETIC existing data')
        with self.assertRaises(FileExistsError):
            bundle.extract(self.archive, target)
        self.assertEqual((target / 'keep.txt').read_bytes(), b'SYNTHETIC existing data')

    def test_source_hash_mismatch_leaves_no_valid_success_archive(self):
        (self.stage / 'README.md').write_bytes(b'changed after approved source hash')
        with self.assertRaisesRegex(ValueError, 'approved hash'):
            self.build()
        with self.assertRaises(ValueError):
            bundle.verify(self.archive)

    def test_corrupt_member_or_extra_inventory_rejected_before_extraction(self):
        good = {'item.json': b'{"SYNTHETIC":true}'}
        for payloads, extra in [({'item.json': b'{"SYNTHETIC":null}'}, None),
                                (good, ('extra.txt', b'SYNTHETIC extra'))]:
            with self.subTest(extra=extra):
                self.crafted(payloads, manifest=self.manifest(good), extra=extra)
                target = self.root / 'must-not-exist'
                with self.assertRaisesRegex(ValueError, 'payload bytes differ' if extra is None else 'inventory'):
                    bundle.extract(self.archive, target)
                self.assertFalse(target.exists())

    def test_unsafe_alias_or_ancestor_paths_rejected_without_output(self):
        bad_maps = [{name: '0' * 64} for name in ['../outside', '/absolute', 'a/./b', 'a//b',
                   'a/../b', 'a\\b', 'C:drive', '', 'dir/', 'nul\x00suffix', 'MANIFEST.json']]
        bad_maps += [{'A': '0' * 64, 'a': '0' * 64}, {'a': '0' * 64, 'a/b': '0' * 64},
                     {'é': '0' * 64, 'e\u0301': '0' * 64}]
        for files in bad_maps:
            with self.subTest(files=files):
                with self.assertRaises(ValueError):
                    bundle.build(self.stage, files, self.archive)
                self.assertFalse(self.archive.exists())
        for name in ['../outside', '/absolute', 'a\\b', 'C:drive']:
            self.crafted({name: b'bad path'})
            with self.assertRaises(ValueError):
                bundle.verify(self.archive)

    def test_source_and_zip_symlinks_are_not_followed(self):
        link = self.stage / 'link'
        link.symlink_to(self.stage / 'README.md')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            bundle.build(self.stage, {'link': self.files['README.md']}, self.archive)
        self.assertFalse(self.archive.exists())
        value = ZipInfo('link')
        value.create_system = 3
        value.external_attr = (stat.S_IFLNK | 0o777) << 16
        with ZipFile(self.archive, 'w') as archive:
            archive.writestr(value, b'../outside')
            archive.writestr(bundle.MANIFEST, json.dumps(self.manifest({'link': b'../outside'})))
        with self.assertRaisesRegex(ValueError, 'regular'):
            bundle.verify(self.archive)

    def test_expanded_size_bound_and_strict_manifest(self):
        with self.assertRaises(ValueError):
            bundle.build(self.stage, self.files, self.archive, max_bytes=1)
        self.assertFalse(self.archive.exists())
        self.build()
        with self.assertRaises(ValueError):
            bundle.verify(self.archive, max_bytes=1)
        for maximum in [True, 0, -1]:
            with self.assertRaises(ValueError):
                bundle.verify(self.archive, max_bytes=maximum)
        for malformed in [b'{"schema_version":1,"schema_version":1,"files":{}}',
                          {'schema_version': True, 'files': {'x': {'sha256': '0' * 64, 'bytes': 1}}},
                          {'schema_version': 1, 'files': {'x': {'sha256': '0' * 64, 'bytes': True}}},
                          {'schema_version': 1, 'files': {'x': {'sha256': '0' * 64, 'bytes': 9}}}]:
            self.crafted({'x': b'x'}, manifest=malformed)
            with self.assertRaises(ValueError):
                bundle.verify(self.archive)

    def test_builder_cannot_seal_an_index_its_verifier_would_reject(self):
        with patch.object(bundle, 'MAX_MANIFEST_BYTES', 50):
            with self.assertRaisesRegex(ValueError, 'bounded success manifest'):
                self.build()
            with self.assertRaisesRegex(ValueError, 'bounded success manifest'):
                bundle.verify(self.archive)

    def test_extracted_readback_detects_changed_added_or_symlinked_files(self):
        self.build()
        for mutation in ['changed', 'extra', 'symlink']:
            target = self.root / mutation
            bundle.extract(self.archive, target)
            path = target / 'README.md'
            if mutation == 'changed':
                path.chmod(0o644)
                path.write_bytes(b'changed payload')
            elif mutation == 'extra':
                (target / 'unexpected').write_bytes(b'extra')
            else:
                path.unlink()
                path.symlink_to(self.stage / 'README.md')
            with self.assertRaises(ValueError):
                bundle.verify_tree(target)

    def test_cli_build_verify_extract_and_readback(self):
        allowlist = self.root / 'reviewed-files.json'
        allowlist.write_text(json.dumps(self.files))
        destination = self.root / 'cli-output'
        for args in [['build', str(self.stage), str(allowlist), str(self.archive)],
                     ['verify', str(self.archive)], ['extract', str(self.archive), str(destination)],
                     ['verify-tree', str(destination)]]:
            result = subprocess.run([sys.executable, '-B', '-m', 'chesslab.bundle', *args],
                                    cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsInstance(json.loads(result.stdout), dict)


if __name__ == '__main__':
    unittest.main()

"""Explicit, hash-checked private reproduction archives. No automatic data selection.

Hashes verify byte integrity, not privacy, scientific validity or source authority.
The operator reviews/stages the export and provides its expected source hashes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import unicodedata
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

MANIFEST = 'MANIFEST.json'
MAX_BYTES = 10_000_000_000
MAX_FILES = 100_000
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
CHUNK = 1024 * 1024


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def _names(names):
    _require(1 <= len(names) <= MAX_FILES, 'bounded nonempty file inventory required')
    canonical = set()
    for name in names:
        _require(isinstance(name, str) and name and '\\' not in name and ':' not in name and
                 '\x00' not in name and all(p not in {'', '.', '..'} for p in name.split('/')),
                 'relative POSIX file paths required')
        key = unicodedata.normalize('NFC', name).casefold()
        _require(key not in canonical, 'duplicate or case/Unicode-alias file name')
        canonical.add(key)
    _require(not any('/'.join(name.split('/')[:i]) in canonical
                     for name in canonical for i in range(1, len(name.split('/')))),
             'a file cannot also be a parent directory')


def _digest(stream, limit=None):
    digest, size = hashlib.sha256(), 0
    while block := stream.read(CHUNK):
        digest.update(block)
        size += len(block)
        _require(limit is None or size <= limit, 'stream exceeds declared byte count')
    return digest.hexdigest(), size


def _hash(value):
    _require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'lowercase SHA256 required')


def _source(root, name):
    path = root
    for part in name.split('/'):
        path /= part
        _require(not path.is_symlink(), 'source symlinks are not exported')
    _require(path.is_file() and path.resolve().is_relative_to(root), 'source must be a regular confined file')
    return path


def _manifest(raw):
    _require(len(raw) <= MAX_MANIFEST_BYTES, 'bounded success manifest required')
    value = _json(raw)
    _require(isinstance(value, dict) and set(value) == {'schema_version', 'files'} and
             type(value['schema_version']) is int and value['schema_version'] == 1 and
             isinstance(value['files'], dict) and value['files'], 'supported complete manifest required')
    _names([*value['files'], MANIFEST])
    for record in value['files'].values():
        _require(isinstance(record, dict) and set(record) == {'sha256', 'bytes'} and
                 type(record['bytes']) is int and record['bytes'] >= 0, 'integer byte count required')
        _hash(record['sha256'])
    return value


def _info(name):
    value = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    value.create_system = 3
    value.external_attr = (stat.S_IFREG | 0o444) << 16
    value.compress_type = ZIP_DEFLATED
    return value


def build(root, files, output, *, max_bytes=MAX_BYTES):
    """Copy only {relative_path: expected_sha256}; never crawl or overwrite."""
    _require(type(max_bytes) is int and max_bytes > 0, 'positive byte allowance required')
    _require(isinstance(files, dict) and files, 'explicit reviewed file/hash mapping required')
    _names([*files, MANIFEST])
    output = Path(output)
    root = Path(root).resolve(strict=True)
    _require(root.is_dir(), 'staged source directory required')
    sources = {}
    for name, expected in files.items():
        _hash(expected)
        sources[name] = _source(root, name)
    _require(sum(p.stat().st_size for p in sources.values()) <= max_bytes, 'payload exceeds byte allowance')
    manifest, total = {'schema_version': 1, 'files': {}}, 0
    # A failed build stays at its original path without a success manifest.
    # Preserve it for diagnosis rather than replacing an earlier archive.
    with ZipFile(output, 'x', compression=ZIP_DEFLATED, allowZip64=True) as archive:
        for name, source in sorted(sources.items()):
            digest, size = hashlib.sha256(), 0
            with source.open('rb') as reader, archive.open(_info(name), 'w', force_zip64=True) as writer:
                while block := reader.read(CHUNK):
                    total += len(block)
                    _require(total <= max_bytes, 'source grew beyond byte allowance')
                    writer.write(block)
                    digest.update(block)
                    size += len(block)
            _require(digest.hexdigest() == files[name], 'source differs from approved hash: ' + name)
            manifest['files'][name] = {'sha256': files[name], 'bytes': size}
        encoded = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
        _require(len(encoded) <= MAX_MANIFEST_BYTES, 'bounded success manifest required')
        archive.writestr(_info(MANIFEST), encoded)
    with Path(output).open('rb') as stream:
        digest, size = _digest(stream)
    return {'archive_sha256': digest, 'archive_bytes': size, 'payload_files': len(files), 'payload_bytes': total}


def _verify(archive, max_bytes):
    _require(type(max_bytes) is int and max_bytes > 0, 'positive byte allowance required')
    infos = archive.infolist()
    _names([info.filename for info in infos])
    for info in infos:
        mode = stat.S_IFMT(info.external_attr >> 16)
        _require(info.orig_filename == info.filename and not info.is_dir() and
                 mode in {0, stat.S_IFREG} and not info.flag_bits & 1 and
                 info.compress_type in {ZIP_STORED, ZIP_DEFLATED}, 'regular unencrypted ZIP files required')
    _require(MANIFEST in archive.namelist() and archive.getinfo(MANIFEST).file_size <= MAX_MANIFEST_BYTES,
             'bounded success manifest required')
    manifest = _manifest(archive.read(MANIFEST))
    _require(set(archive.namelist()) == set(manifest['files']) | {MANIFEST}, 'ZIP inventory differs from manifest')
    total = 0
    for name, record in manifest['files'].items():
        _require(archive.getinfo(name).file_size == record['bytes'], 'ZIP and manifest sizes differ')
        total += record['bytes']
        _require(total <= max_bytes, 'expanded payload exceeds byte allowance')
    for name, record in manifest['files'].items():
        with archive.open(name) as stream:
            digest, size = _digest(stream, record['bytes'])
        _require(digest == record['sha256'] and size == record['bytes'], 'payload bytes differ: ' + name)
    return manifest


def verify(path, *, max_bytes=MAX_BYTES):
    """Check exact member inventory, regular paths, sizes and every payload hash."""
    with ZipFile(path) as archive:
        return _verify(archive, max_bytes)


def extract(path, destination, *, max_bytes=MAX_BYTES):
    """Verify everything first, then create a NEW destination; never overwrite."""
    destination = Path(destination)
    with ZipFile(path) as archive:
        manifest = _verify(archive, max_bytes)
        destination.mkdir(parents=True, exist_ok=False)
        for name, record in manifest['files'].items():
            target = destination.joinpath(*name.split('/'))
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as reader, target.open('xb') as writer:
                digest, size = hashlib.sha256(), 0
                while block := reader.read(CHUNK):
                    writer.write(block)
                    digest.update(block)
                    size += len(block)
            _require(digest.hexdigest() == record['sha256'] and size == record['bytes'], 'archive changed during extraction')
            target.chmod(0o444)
        with (destination / MANIFEST).open('xb') as stream:
            stream.write(archive.read(MANIFEST))
        (destination / MANIFEST).chmod(0o444)
    return manifest


def verify_tree(directory, *, max_bytes=MAX_BYTES):
    """Read back the extracted payload, including unexpected files and symlinks."""
    _require(type(max_bytes) is int and max_bytes > 0, 'positive byte allowance required')
    root = Path(directory).resolve(strict=True)
    manifest_path = _source(root, MANIFEST)
    _require(manifest_path.stat().st_size <= MAX_MANIFEST_BYTES, 'bounded success manifest required')
    manifest = _manifest(manifest_path.read_bytes())
    actual = set()
    for path in root.rglob('*'):
        _require(not path.is_symlink(), 'extracted symlinks are not permitted')
        if path.is_file():
            actual.add(str(path.relative_to(root)))
            _require(len(actual) <= MAX_FILES, 'extracted inventory exceeds file allowance')
    _require(actual == set(manifest['files']) | {MANIFEST}, 'extracted file inventory differs from manifest')
    _require(sum(r['bytes'] for r in manifest['files'].values()) <= max_bytes, 'expanded payload exceeds byte allowance')
    for name, record in manifest['files'].items():
        source = _source(root, name)
        _require(source.stat().st_size == record['bytes'], 'extracted size differs: ' + name)
        with source.open('rb') as stream:
            digest, size = _digest(stream, record['bytes'])
        _require(digest == record['sha256'] and size == record['bytes'], 'extracted payload bytes differ: ' + name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    creator = commands.add_parser('build')
    creator.add_argument('root', type=Path)
    creator.add_argument('files', type=Path, help='reviewed JSON object {relative_path: expected_sha256}')
    creator.add_argument('output', type=Path)
    checker = commands.add_parser('verify')
    checker.add_argument('archive', type=Path)
    extractor = commands.add_parser('extract')
    extractor.add_argument('archive', type=Path)
    extractor.add_argument('destination', type=Path)
    tree = commands.add_parser('verify-tree')
    tree.add_argument('directory', type=Path)
    for command in [creator, checker, extractor, tree]:
        command.add_argument('--max-bytes', type=int, default=MAX_BYTES)
    args = parser.parse_args()
    if args.action == 'build':
        summary = build(args.root, _json(args.files.read_bytes()), args.output, max_bytes=args.max_bytes)
    else:
        if args.action == 'verify-tree':
            manifest = verify_tree(args.directory, max_bytes=args.max_bytes)
        elif args.action == 'verify':
            manifest = verify(args.archive, max_bytes=args.max_bytes)
        else:
            manifest = extract(args.archive, args.destination, max_bytes=args.max_bytes)
        summary = {'verified_files': len(manifest['files']),
                   'payload_bytes': sum(r['bytes'] for r in manifest['files'].values())}
    print(json.dumps(summary))


if __name__ == '__main__':
    main()

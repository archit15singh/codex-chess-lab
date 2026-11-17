"""Snapshot only mechanical collection code before a live experiment."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

FILES = ('chesslab/__init__.py', 'chesslab/__main__.py', 'chesslab/ledger.py',
         'chesslab/stats.py', 'scripts/browser_collector.mjs')

FRIEND_MATCH_FILES = tuple(f'scripts/friend-match/{name}' for name in (
    'browser.mjs', 'cli.mjs', 'match.mjs', 'models.mjs', 'package.json', 'package-lock.json',
))


def freeze(source: Path, destination: Path, *, friend_match: bool = False) -> dict:
    source = source.resolve(strict=True)
    # Read the small allowlist first. No repository crawl or evaluator copy.
    content = {}
    runtime_files = FRIEND_MATCH_FILES if friend_match else FILES
    for relative in runtime_files:
        path = (source / relative).resolve(strict=True)
        if not path.is_relative_to(source) or not path.is_file():
            raise ValueError('mechanical source escapes source directory')
        content[relative] = path.read_bytes()
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for relative, data in content.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        target.chmod(0o444)
        hashes[relative] = hashlib.sha256(data).hexdigest()
    manifest = {'schema_version': 1, 'frozen_at': datetime.now(timezone.utc).isoformat(),
                'source': str(source), 'purpose': 'mechanical collector only; no evaluator',
                'files': hashes}
    if friend_match:
        manifest['profile'] = 'friend-match'
    path = destination / 'manifest.json'
    with path.open('x') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    path.chmod(0o444)
    verify(destination)
    return manifest


def verify(directory: Path) -> dict:
    manifest = json.loads((directory / 'manifest.json').read_text())
    expected_files = FRIEND_MATCH_FILES if manifest.get('profile') == 'friend-match' else FILES
    if set(manifest['files']) != set(expected_files):
        raise ValueError('unexpected mechanical runtime inventory')
    for relative, expected in manifest['files'].items():
        actual = hashlib.sha256((directory / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'frozen runtime changed: {relative}')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--friend-match', action='store_true', help='freeze the Brave friend-match controller')
    args = parser.parse_args()
    manifest = (verify(args.destination) if args.check else
                freeze(args.source, args.destination, friend_match=args.friend_match))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()

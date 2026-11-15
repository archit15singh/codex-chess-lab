"""python -m chesslab: collect evidence; never select or execute chess moves."""
import argparse
import json
import sys
from pathlib import Path
from .ledger import Ledger, digest
from .stats import summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path('evidence/private/runs.sqlite'))
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('run')
    create.add_argument('config', type=Path)
    event = sub.add_parser('append')
    event.add_argument('run')
    event.add_argument('kind')
    event.add_argument('payload', help='JSON file, or - for stdin')
    event.add_argument('--artifact', type=Path, help='Read and hash a screenshot file before appending')
    export = sub.add_parser('export')
    export.add_argument('run')
    sha = sub.add_parser('hash')
    sha.add_argument('path', type=Path)
    summary = sub.add_parser('summarize')
    summary.add_argument('exports', nargs='+', type=Path)
    args = parser.parse_args()
    if args.command == 'hash':
        print(digest(args.path))
        return
    if args.command == 'summarize':
        print(json.dumps(summarize([json.loads(p.read_text()) for p in args.exports]), indent=2))
        return
    ledger = Ledger(args.db)
    if args.command == 'create':
        ledger.create(args.run, json.loads(args.config.read_text()))
    elif args.command == 'append':
        payload = json.loads(sys.stdin.read() if args.payload == '-' else Path(args.payload).read_text())
        if args.artifact is not None:
            artifact = args.artifact.resolve(strict=True)
            payload['screenshot_sha256'] = digest(artifact)
            payload['screenshot_path'] = str(artifact)
        ledger.append(args.run, args.kind, payload)
    else:
        print(json.dumps(ledger.export(args.run), indent=2))


if __name__ == '__main__':
    main()

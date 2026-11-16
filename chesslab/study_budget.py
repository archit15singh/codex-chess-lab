"""Append-only assignment reservations for one bounded research program.

Reserve before launch, including failures and retries. This counts planned use;
it neither starts actors nor enforces a running actor's wall-clock deadline.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


DEFAULT_LIMITS = {
    'games': 64, 'diagnostics': 512, 'move_decisions': 4000, 'candidates': 3,
    'pilot_games': 8, 'pilot_diagnostics': 48,
}


def positive_counts(value):
    if (not isinstance(value, dict) or not value
            or any(not isinstance(k, str) or not k or type(v) is not int or v <= 0
                   for k, v in value.items())):
        raise ValueError('expected named positive integer counts')
    return value


def create(path: Path, limits=None):
    limits = positive_counts(dict(DEFAULT_LIMITS) if limits is None else limits)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents an invocation from resetting an existing cap.
    with path.open('xb'):
        pass
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''
            CREATE TABLE limits (name TEXT PRIMARY KEY, amount INTEGER NOT NULL);
            CREATE TABLE reservations (
                identity TEXT PRIMARY KEY, at TEXT NOT NULL,
                usage TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE TRIGGER limits_no_update BEFORE UPDATE ON limits
                BEGIN SELECT RAISE(ABORT, 'immutable limits'); END;
            CREATE TRIGGER limits_no_delete BEFORE DELETE ON limits
                BEGIN SELECT RAISE(ABORT, 'immutable limits'); END;
            CREATE TRIGGER reservations_no_update BEFORE UPDATE ON reservations
                BEGIN SELECT RAISE(ABORT, 'append-only reservations'); END;
            CREATE TRIGGER reservations_no_delete BEFORE DELETE ON reservations
                BEGIN SELECT RAISE(ABORT, 'append-only reservations'); END;
        ''')
        db.executemany('INSERT INTO limits VALUES (?, ?)', limits.items())
        db.execute('''CREATE TRIGGER limits_no_insert BEFORE INSERT ON limits
                   BEGIN SELECT RAISE(ABORT, 'immutable limits'); END''')
    return summary(path)


def connect(path):
    # URI mode=rw fails closed when a checkpoint names a missing database.
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True,
                           timeout=10, isolation_level=None)


def snapshot(db):
    limits = dict(db.execute('SELECT name, amount FROM limits'))
    positive_counts(limits)
    used = dict.fromkeys(limits, 0)
    assignments = []
    for identity, at, raw, metadata in db.execute('SELECT * FROM reservations ORDER BY rowid'):
        usage = positive_counts(json.loads(raw))
        if set(usage) - limits.keys():
            raise ValueError('reservation contains an unknown resource')
        for name, count in usage.items():
            used[name] += count
        assignments.append({'identity': identity, 'at': at, 'usage': usage,
                            'metadata': json.loads(metadata)})
    if any(used[k] > limits[k] for k in limits):
        raise ValueError('existing ledger exceeds its cap')
    return {'limits': limits, 'used': used,
            'remaining': {k: limits[k] - used[k] for k in limits},
            'reservations': assignments}


def reserve(path, identity, usage, *, metadata=None):
    positive_counts(usage)
    for pilot, total in [('pilot_games', 'games'), ('pilot_diagnostics', 'diagnostics')]:
        if usage.get(pilot, 0) > usage.get(total, 0):
            raise ValueError('pilot reservations must also consume the total cap')
    if not isinstance(identity, str) or not 1 <= len(identity) <= 200:
        raise ValueError('reservation identity must contain 1..200 characters')
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError('metadata must be an object')
    encoded_metadata = json.dumps({} if metadata is None else metadata, allow_nan=False)
    with closing(connect(path)) as db:
        try:
            db.execute('BEGIN IMMEDIATE')
            state = snapshot(db)
            if set(usage) - state['limits'].keys():
                raise ValueError('unknown resource')
            if any(count > state['remaining'][name] for name, count in usage.items()):
                raise ValueError('study resource cap reached; reservation refused')
            at = datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO reservations VALUES (?, ?, ?, ?)',
                       (identity, at, json.dumps(usage, sort_keys=True), encoded_metadata))
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return {'identity': identity, 'at': at, 'usage': dict(usage)}


def summary(path):
    with closing(connect(path)) as db:
        db.execute('BEGIN')
        return snapshot(db)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'reserve', 'summary'])
    parser.add_argument('path', type=Path)
    parser.add_argument('--identity')
    parser.add_argument('--usage', type=Path, help='JSON file containing counts')
    args = parser.parse_args()
    if args.action == 'create':
        result = create(args.path)
    elif args.action == 'summary':
        result = summary(args.path)
    else:
        if args.identity is None or args.usage is None:
            parser.error('reserve requires --identity and --usage')
        result = reserve(args.path, args.identity, json.loads(args.usage.read_text()))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

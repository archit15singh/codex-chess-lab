"""One append-only budget for engine active wall time across a study.

Reserve before starting work. Pending or unmeasured operations retain their full
allowance. Settle only after independently recording process termination and all
startup/search/cleanup segments. Idle time between game turns is excluded.
This ledger accounts for time; the caller must enforce process watchdogs.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import sqlite3


def nanoseconds(seconds):
    if type(seconds) not in (str, int, float, Decimal):
        raise ValueError('finite positive seconds required')
    try:
        value = Decimal(str(seconds))
    except InvalidOperation as exc:
        raise ValueError('finite positive seconds required') from exc
    if not value.is_finite() or not 0 < value <= 86400:
        raise ValueError('seconds must be positive and at most one day')
    return int((value * 1_000_000_000).to_integral_value(rounding=ROUND_CEILING))


def _connect(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True,
                           isolation_level=None, timeout=10)


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def create(path, seconds=7200, *, provenance):
    limit = nanoseconds(seconds)
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError('prospective limit provenance required')
    encoded = _json(provenance)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb'):
        pass
    with closing(_connect(path)) as db, db:
        db.executescript('''
            CREATE TABLE policy (limit_ns INTEGER NOT NULL, provenance TEXT NOT NULL);
            CREATE TABLE reservations (identity TEXT PRIMARY KEY, at TEXT NOT NULL,
                reserved_ns INTEGER NOT NULL, metadata TEXT NOT NULL);
            CREATE TABLE settlements (identity TEXT PRIMARY KEY REFERENCES reservations,
                at TEXT NOT NULL, active_ns INTEGER NOT NULL,
                receipt_path TEXT NOT NULL, receipt_sha256 TEXT NOT NULL);
        ''')
        db.execute('INSERT INTO policy VALUES (?, ?)', (limit, encoded))
        for table in ['policy', 'reservations', 'settlements']:
            for action in ['UPDATE', 'DELETE'] + (['INSERT'] if table == 'policy' else []):
                db.execute(f'''CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action}
                    ON {table} BEGIN SELECT RAISE(ABORT, 'append-only engine budget'); END''')
    return summary(path)


def _receipt(path, expected_ns):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    value = json.loads(raw)
    if (not isinstance(value, dict) or value.get('process_stopped') is not True
            or type(value.get('active_ns')) is not int or value['active_ns'] != expected_ns):
        raise ValueError('matching active duration and proven process exit receipt required')
    return str(path), hashlib.sha256(raw).hexdigest()


def _snapshot(db):
    policies = db.execute('SELECT * FROM policy').fetchall()
    if len(policies) != 1 or type(policies[0][0]) is not int or policies[0][0] <= 0:
        raise ValueError('invalid existing engine policy; never reset')
    limit, provenance = policies[0]
    finished = {row[0]: row for row in db.execute('SELECT * FROM settlements')}
    operations = []
    for identity, at, reserved, metadata in db.execute('SELECT * FROM reservations ORDER BY rowid'):
        if type(reserved) is not int or reserved <= 0:
            raise ValueError('invalid engine reservation')
        charge, status = reserved, 'full_reservation_retained'
        extra = {}
        if identity in finished:
            _, ended, active, path, expected = finished.pop(identity)
            if type(active) is not int or active < 0 or _receipt(path, active)[1] != expected:
                raise ValueError('settlement receipt changed or invalid')
            charge, status = active, 'measured'
            extra = {'settled_at': ended, 'receipt_path': path, 'receipt_sha256': expected,
                     'overrun': active > reserved}
        operations.append({'identity': identity, 'at': at, 'reserved_ns': reserved,
                           'charged_ns': charge, 'status': status,
                           'metadata': json.loads(metadata), **extra})
    if finished:
        raise ValueError('orphan engine settlement')
    charged = sum(row['charged_ns'] for row in operations)
    return {'limit_ns': limit, 'charged_ns': charged, 'remaining_ns': max(0, limit - charged),
            'over_cap': charged > limit, 'provenance': json.loads(provenance),
            'operations': operations}


def summary(path):
    with closing(_connect(path)) as db:
        db.execute('BEGIN')
        return _snapshot(db)


def reserve(path, identity, seconds, *, metadata):
    amount = nanoseconds(seconds)
    if not isinstance(identity, str) or not 1 <= len(identity) <= 200:
        raise ValueError('unique operation identity required')
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError('operation provenance required')
    encoded = _json(metadata)
    with closing(_connect(path)) as db:
        try:
            db.execute('BEGIN IMMEDIATE')
            state = _snapshot(db)
            if state['over_cap'] or amount > state['remaining_ns']:
                raise ValueError('engine active-time cap reached; reservation refused')
            db.execute('INSERT INTO reservations VALUES (?, ?, ?, ?)',
                       (identity, datetime.now(timezone.utc).isoformat(), amount, encoded))
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return {'identity': identity, 'reserved_ns': amount}


def settle(path, identity, active_ns, *, receipt):
    if type(active_ns) is not int or active_ns < 0:
        raise ValueError('nonnegative measured integer nanoseconds required')
    receipt_path, receipt_sha = _receipt(receipt, active_ns)
    with closing(_connect(path)) as db:
        try:
            db.execute('BEGIN IMMEDIATE')
            _snapshot(db)
            row = db.execute('SELECT reserved_ns FROM reservations WHERE identity=?', (identity,)).fetchone()
            if not row:
                raise ValueError('existing engine reservation required')
            db.execute('INSERT INTO settlements VALUES (?, ?, ?, ?, ?)',
                       (identity, datetime.now(timezone.utc).isoformat(), active_ns, receipt_path, receipt_sha))
            db.commit()
        except BaseException:
            db.rollback()
            raise
    # Preserve the full observed charge before raising. Never hide an overrun by
    # discarding a result or retaining a smaller nominal allowance.
    if active_ns > row[0]:
        raise TimeoutError('engine allowance overrun recorded; inspect before further work')
    return {'identity': identity, 'charged_ns': active_ns, 'receipt_sha256': receipt_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'reserve', 'settle', 'summary'])
    parser.add_argument('path', type=Path)
    parser.add_argument('--seconds', default='7200')
    parser.add_argument('--identity')
    parser.add_argument('--metadata', type=Path)
    parser.add_argument('--active-ns', type=int)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.action in {'create', 'reserve'} and args.metadata is None:
        parser.error('create/reserve require --metadata JSON provenance')
    if args.action == 'create':
        result = create(args.path, args.seconds, provenance=json.loads(args.metadata.read_bytes()))
    elif args.action == 'reserve':
        result = reserve(args.path, args.identity, args.seconds, metadata=json.loads(args.metadata.read_bytes()))
    elif args.action == 'settle':
        if args.receipt is None:
            parser.error('settle requires --receipt')
        result = settle(args.path, args.identity, args.active_ns, receipt=args.receipt)
    else:
        result = summary(args.path)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

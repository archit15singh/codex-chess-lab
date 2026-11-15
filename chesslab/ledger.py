"""A transactional, append-only record of experiments and attempted actions.

This is an audit aid, not a security sandbox: operator tool traces must also be
reviewed. It deliberately imports no chess library and never returns moves.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASELINE = frozenset({'screenshot', 'coordinate_click'})
CAPABILITIES = BASELINE | {'validated_state', 'history', 'legality', 'search', 'reflection'}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Ledger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY, config TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY, run TEXT NOT NULL REFERENCES runs(id),
          kind TEXT NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS immutable_runs_update BEFORE UPDATE ON runs
          BEGIN SELECT RAISE(ABORT, 'immutable'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_runs_delete BEFORE DELETE ON runs
          BEGIN SELECT RAISE(ABORT, 'immutable'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_events_update BEFORE UPDATE ON events
          BEGIN SELECT RAISE(ABORT, 'immutable'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_events_delete BEFORE DELETE ON events
          BEGIN SELECT RAISE(ABORT, 'immutable'); END;
        ''')

    def create(self, run: str, config: dict) -> None:
        required = {'condition', 'capabilities', 'model', 'reasoning', 'seed', 'purpose', 'permission'}
        if set(config) != required:
            raise ValueError(f'config requires exactly {sorted(required)}')
        caps = config['capabilities']
        if not isinstance(caps, list) or not caps or not set(caps) <= CAPABILITIES:
            raise ValueError('unknown or empty capabilities')
        if config['condition'] == 'unaided' and set(caps) != BASELINE:
            raise ValueError('unaided must have screenshot and coordinate_click only')
        if config['purpose'] not in {'feasibility', 'pilot', 'heldout', 'training', 'synthetic'}:
            raise ValueError('unknown purpose')
        for field in ('condition', 'model', 'reasoning', 'permission'):
            if not isinstance(config[field], str) or not config[field].strip():
                raise ValueError(f'{field} must be recorded')
        if type(config['seed']) is not int:
            raise ValueError('seed must be an integer')
        with self.db:
            self.db.execute('INSERT INTO runs VALUES (?,?,?)', (run, canonical(config), self.now()))

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def events(self, run: str) -> list[dict]:
        return [dict(seq=row[0], kind=row[1], payload=json.loads(row[2]), created=row[3])
                for row in self.db.execute('SELECT seq,kind,payload,created FROM events WHERE run=? ORDER BY seq', (run,))]

    def append(self, run: str, kind: str, payload: dict) -> None:
        """Reserve before clicking; resolve before reserving again. Never retry blindly."""
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT config FROM runs WHERE id=?', (run,)).fetchone()
            if row is None:
                raise ValueError('unknown run')
            config = json.loads(row[0])
            events = self.events(run)
            pending = None
            attempts = set()
            terminal = False
            for event in events:
                if event['kind'] == 'intent':
                    pending = event['payload']['action_id']
                    attempts.add(pending)
                elif (event['kind'] == 'verification'
                      and event['payload']['outcome'] != 'uncertain'):
                    pending = None
                elif event['kind'] == 'terminal':
                    terminal = True
            if terminal:
                raise ValueError('run already terminal')
            if kind == 'intent':
                if pending is not None:
                    raise ValueError('unresolved action: inspect screen before retry')
                if not {'action_id', 'move', 'screenshot_sha256'} <= payload.keys():
                    raise ValueError('intent requires action_id, move, screenshot_sha256')
                if not payload['action_id'] or payload['action_id'] in attempts:
                    raise ValueError('duplicate or empty action_id')
                self._hash(payload['screenshot_sha256'])
            elif kind == 'verification':
                if pending is None or payload.get('action_id') != pending:
                    raise ValueError('verification must resolve pending action')
                if payload.get('outcome') not in {'executed', 'not_executed', 'uncertain'}:
                    raise ValueError('invalid verification outcome')
                self._hash(payload.get('screenshot_sha256'))
                # Preserve uncertainty as evidence without resolving the action.
                # A later conclusive verification must establish what happened.
            elif kind == 'tool':
                if payload.get('capability') not in config['capabilities']:
                    raise ValueError('prohibited capability for condition')
            elif kind == 'terminal':
                if pending is not None:
                    raise ValueError('resolve action before terminal')
                if payload.get('result') not in {'win', 'loss', 'draw', 'aborted'}:
                    raise ValueError('invalid terminal result')
                self._hash(payload.get('screenshot_sha256'))
            elif kind != 'observation':
                raise ValueError('unknown event kind')
            self.db.execute('INSERT INTO events(run,kind,payload,created) VALUES (?,?,?,?)',
                            (run, kind, canonical(payload), self.now()))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    @staticmethod
    def _hash(value: object) -> None:
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('expected SHA-256 hex digest')

    def export(self, run: str) -> dict:
        row = self.db.execute('SELECT config,created FROM runs WHERE id=?', (run,)).fetchone()
        if row is None:
            raise ValueError('unknown run')
        return {'run': run, 'config': json.loads(row[0]), 'created': row[1], 'events': self.events(run)}

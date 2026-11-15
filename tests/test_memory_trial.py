import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chesslab import memory_trial as m
from chesslab import position_trial as static


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(root):
    corpus = root / 'corpus'
    rules = {'side_to_move': 'white', 'castling': {c: {w: True for w in ('kingside', 'queenside')}
              for c in ('white', 'black')}, 'en_passant_square': None, 'halfmove_clock': 0}
    frames = []
    for ply in range(25):
        image = corpus / 'images' / f'{ply}.png'
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b'\x89PNG\r\n\x1a\n' + str(ply).encode())
        frames.append({'ply': ply, 'image': {'path': f'images/{ply}.png', 'sha256': static.sha(image)}})
    sequence = {'sequence_id': 's-test', 'orientation': 'white', 'initial_rules': rules,
                'checkpoints': [6, 12, 18, 24], 'frames': frames}
    dump(corpus / 'player/sequences.json', {'schema_version': 1, 'sequences': [sequence,
         {**sequence, 'sequence_id': 'DO-NOT-DISCLOSE'}]})
    seal(corpus)
    return corpus


def seal(corpus):
    dump(corpus / 'manifest.json', {'status': 'sealed', 'files': {
        str(p.relative_to(corpus)): static.sha(p) for p in corpus.rglob('*')
        if p.is_file() and p.name != 'manifest.json'}})


def response():
    return {'last_move_uci': None, 'piece_map': {s: '.' for s in static.SQUARES},
            'side_to_move': 'unknown', 'confidence': 0.3,
            'castling': {c: {w: 'unknown' for w in ('kingside', 'queenside')} for c in ('white', 'black')},
            'en_passant_square': 'unknown', 'recall': {'d4': '?', 'e5': '?'}}


class MemoryTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = fixture(self.root)
        self.directory = self.root / 'trial'
        self.time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.clock = patch.object(static, 'now', side_effect=lambda: self.time)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def prepare(self, condition='internal'):
        return m.prepare(self.corpus, 's-test', condition, self.directory)

    def submit(self, stage, value=None, raw=None):
        p = self.root / f'answer-{stage}.json'
        p.write_bytes(raw if raw is not None else json.dumps(response() if value is None else value).encode())
        return m.submit(self.directory, stage, p)

    def test_incremental_delivery_reopen_and_own_record_only(self):
        self.prepare('record')
        first = m.open_next(self.directory)
        self.assertEqual([f['ply'] for f in first['frames']], list(range(7)))
        self.assertEqual(first['own_prior_responses'], [])
        self.assertNotIn('DO-NOT-DISCLOSE', json.dumps(first))
        self.time += timedelta(seconds=10)
        self.assertEqual(m.open_next(self.directory), first)
        raw = b'\n ' + json.dumps(response(), indent=2).encode() + b'\n'
        self.submit(1, raw=raw)
        second = m.open_next(self.directory)
        self.assertEqual([f['ply'] for f in second['frames']], list(range(7, 13)))
        self.assertNotIn('initial_rules', second)
        self.assertEqual(base64.b64decode(second['own_prior_responses'][0]['raw_base64']), raw)
        self.assertEqual(second['own_prior_responses'][0]['raw_utf8'], raw.decode())
        self.assertEqual(second['recall_checkpoint_ply'], 6)
        with self.assertRaises(FileExistsError):
            self.submit(1)

    def test_internal_no_external_record_or_future_frame(self):
        self.prepare()
        first = m.open_next(self.directory)
        self.assertNotIn('own_prior_responses', first)
        self.submit(1)
        second = m.open_next(self.directory)
        self.assertNotIn('own_prior_responses', second)
        self.assertEqual(max(f['ply'] for f in second['frames']), 12)
        self.assertFalse(m.stage_path(self.directory, 3).exists())

    def test_late_malformed_missing_preserved_and_stop(self):
        self.prepare()
        m.open_next(self.directory)
        self.time += timedelta(seconds=60)
        saved = self.submit(1)
        self.assertTrue(saved['late'])
        self.assertEqual(m.open_next(self.directory)['status'], 'stopped')
        self.assertFalse(m.stage_path(self.directory, 2).exists())
        other = self.root / 'malformed'
        m.prepare(self.corpus, 's-test', 'internal', other)
        m.open_next(other)
        p = self.root / 'malformed-answer'
        p.write_bytes(b'{"bad":1,"bad":2}')
        self.assertFalse(m.submit(other, 1, p)['format_valid'])
        record = m.read_record(m.stage_path(other, 1))
        self.assertEqual(base64.b64decode(record['raw_base64']), p.read_bytes())
        self.assertEqual(m.open_next(other)['reason'], 'malformed')
        missing = self.root / 'missing'
        m.prepare(self.corpus, 's-test', 'internal', missing)
        opened = m.open_next(missing)
        self.time += timedelta(seconds=60)
        self.assertEqual(m.open_next(missing)['reason'], 'missing_at_deadline')
        self.assertEqual(json.loads((m.stage_path(missing, 1) / 'open.json').read_text()), opened)

    def test_tamper_and_concurrent_mutation_rejected(self):
        self.prepare()
        m.open_next(self.directory)
        self.submit(1)
        path = m.stage_path(self.directory, 1) / 'response.json'
        record = json.loads(path.read_text())
        record['raw_base64'] = base64.b64encode(b'{}').decode()
        dump(path, record)
        with self.assertRaisesRegex(ValueError, 'commitment mismatch'):
            m.open_next(self.directory)
        with m.exclusive(self.directory):
            with self.assertRaises(FileExistsError):
                m.open_next(self.directory)
        (self.corpus / 'images/0.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'input or source changed'):
            m.open_next(self.directory)

    def test_deadline_tamper_and_oracle_metadata_rejected(self):
        self.prepare()
        m.open_next(self.directory)
        path = m.stage_path(self.directory, 1) / 'open.json'
        opened = json.loads(path.read_text())
        opened['deadline'] = (self.time + timedelta(seconds=120)).isoformat()
        dump(path, opened)
        with self.assertRaisesRegex(ValueError, 'chronology/deadline'):
            m.open_next(self.directory)
        source = self.corpus / 'player/sequences.json'
        data = json.loads(source.read_text())
        data['sequences'][0]['initial_rules']['fen'] = 'forbidden oracle'
        dump(source, data)
        seal(self.corpus)
        with self.assertRaisesRegex(ValueError, 'metadata fields'):
            m.prepare(self.corpus, 's-test', 'internal', self.root / 'oracle')

    def test_schema_strict_and_mechanics_does_not_import_chess(self):
        m.validate_response(response())
        for changed in ({**response(), 'move': 'a1a2'}, {**response(), 'last_move_uci': 'no'},
                        {**response(), 'recall': {'d4': '.', 'e5': '.', 'a1': '.'}}):
            with self.assertRaises(ValueError):
                m.validate_response(changed)
        code = "import sys; from chesslab import memory_trial; assert 'chess' not in sys.modules"
        subprocess.run([sys.executable, '-c', code], check=True)


if __name__ == '__main__':
    unittest.main()

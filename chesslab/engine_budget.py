"""Shared local engine-work accounting for one sealed supplementary corpus.

Every later assistance/reference operation must hold engine_allowance around
startup, search, and cleanup. This is accounting and serialization, not a timer:
callers must enforce their watchdog within the reserved duration. All writes
reuse the locked inode; replacing a flocked file would split the lock domain.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

LIMIT_SECONDS = 1800.0


@dataclass(frozen=True)
class Allowance:
    budget_path: Path
    reservation_id: int
    allowed_seconds: float
    remaining_seconds: float
    charged_before_seconds: float


def _seconds(value, label, *, positive=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0 or (positive and value == 0)):
        raise ValueError(f'{label} must be finite nonnegative seconds')
    return float(value)


def _read(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    with os.fdopen(os.dup(fd), 'r', encoding='utf-8') as stream:
        return json.load(stream)


def _persist(fd, value):
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    # A partial write is deliberately corrupt/fail-closed after interruption.
    # Do not atomically replace this file: flock refers to its inode.
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    view = memoryview(encoded)
    while view:
        written = os.write(fd, view)
        if not written:
            raise OSError('engine budget write made no progress')
        view = view[written:]
    os.fsync(fd)


def _validate(state, manifest_sha, generation):
    if not isinstance(state, dict) or state.get('schema_version') != 1:
        raise ValueError('invalid engine budget schema; existing budget is not reset')
    if state.get('corpus_manifest_sha256') != manifest_sha:
        raise ValueError('corpus manifest identity changed')
    if (state.get('limit_seconds') != LIMIT_SECONDS
            or state.get('generation_seconds') != generation):
        raise ValueError('engine budget provenance changed')
    records = state.get('operations')
    if not isinstance(records, list):
        raise ValueError('invalid engine budget operations')
    charges = []
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict) or record.get('reservation_id') != index:
            raise ValueError('invalid engine reservation identity')
        reserved = _seconds(record.get('reserved_seconds'), 'reservation', positive=True)
        charge = _seconds(record.get('charged_seconds'), 'charge')
        if not isinstance(record.get('operation'), str) or not record['operation']:
            raise ValueError('invalid engine operation name')
        if record.get('status') == 'reserved':
            if charge != reserved or record.get('actual_seconds') is not None:
                raise ValueError('invalid interrupted reservation charge')
        elif record.get('status') in ('completed', 'failed'):
            if _seconds(record.get('actual_seconds'), 'actual duration') != charge:
                raise ValueError('invalid measured reservation charge')
        else:
            raise ValueError('invalid engine reservation status')
        charges.append(charge)
    total = _seconds(state.get('charged_seconds'), 'total charge')
    if not math.isclose(total, generation + sum(charges), rel_tol=0, abs_tol=1e-9):
        raise ValueError('engine budget total differs from recorded charges')


@contextmanager
def engine_allowance(corpus: Path, operation: str, reserve_seconds: float):
    """Reserve, fsync, yield an Allowance, then charge measured wall duration.

    The exclusive flock covers the entire operation. A process killed inside
    the context leaves the full reservation charged. An existing empty/corrupt
    file, changed manifest or inconsistent ledger fails closed without reset.
    Caller exceptions propagate after their measured duration is recorded.
    Overruns are charged in full and fail an otherwise successful operation.
    An original body exception remains the propagated exception on an overrun.
    """
    reserve = _seconds(reserve_seconds, 'reserve_seconds', positive=True)
    if reserve > LIMIT_SECONDS:
        raise ValueError('reservation exceeds study engine-work limit')
    if not isinstance(operation, str) or not 1 <= len(operation) <= 200:
        raise ValueError('operation must be a name of 1..200 characters')
    corpus = Path(corpus).resolve(strict=True)
    path = corpus.parent / (corpus.name + '-engine-budget.json')
    flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
    except FileExistsError:
        fd = os.open(path, flags)
        created = False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        observed = os.fstat(fd)
        named = path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(observed.st_mode)
                or (observed.st_dev, observed.st_ino) != (named.st_dev, named.st_ino)):
            raise ValueError('engine budget must remain the same regular file')
        raw_manifest = (corpus / 'manifest.json').read_bytes()
        manifest_sha = hashlib.sha256(raw_manifest).hexdigest()
        manifest = json.loads(raw_manifest)
        if not isinstance(manifest, dict) or manifest.get('status') != 'sealed':
            raise ValueError('engine budget requires a sealed corpus manifest')
        generation = _seconds(manifest.get('engine_work_seconds'), 'generation engine work')
        if generation > LIMIT_SECONDS:
            raise ValueError('generation already exceeded study engine-work limit')
        if created:
            state = {'schema_version': 1, 'corpus_manifest_sha256': manifest_sha,
                     'limit_seconds': LIMIT_SECONDS, 'generation_seconds': generation,
                     'charged_seconds': generation, 'operations': []}
            _persist(fd, state)
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        else:
            try:
                state = _read(fd)
            except (ValueError, UnicodeError) as exc:
                raise ValueError('existing engine budget is empty/corrupt; not reset') from exc
            _validate(state, manifest_sha, generation)
        before = state['charged_seconds']
        if LIMIT_SECONDS - before < reserve:
            raise ValueError('insufficient study engine-work budget for full reservation')
        record = {'reservation_id': len(state['operations']) + 1, 'operation': operation,
                  'reserved_seconds': reserve, 'charged_seconds': reserve,
                  'actual_seconds': None, 'status': 'reserved'}
        state['operations'].append(record)
        state['charged_seconds'] = generation + sum(r['charged_seconds'] for r in state['operations'])
        _persist(fd, state)
        allowance = Allowance(path, record['reservation_id'], reserve,
                              LIMIT_SECONDS - state['charged_seconds'], before)
        started = time.monotonic()
        try:
            yield allowance
        except BaseException as exc:
            record['status'] = 'failed'
            record['failure_type'] = type(exc).__name__
            raise
        else:
            record['status'] = 'completed'
        finally:
            elapsed = time.monotonic() - started
            if not math.isfinite(elapsed) or elapsed < 0:
                # Preserve the already-fsynced reservation on a bad clock.
                raise ValueError('engine duration measurement invalid; reservation retained')
            record['actual_seconds'] = record['charged_seconds'] = elapsed
            record['reservation_overrun'] = elapsed > reserve
            raise_overrun = record['reservation_overrun'] and record['status'] == 'completed'
            if raise_overrun:
                record['status'] = 'failed'
                record['failure_type'] = 'TimeoutError'
            state['charged_seconds'] = generation + sum(r['charged_seconds'] for r in state['operations'])
            _persist(fd, state)
            if raise_overrun:
                raise TimeoutError('engine operation exceeded its reserved duration')
    finally:
        os.close(fd)  # Releases flock, including all exceptional paths.

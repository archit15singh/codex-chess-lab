# V2 engine work accounting

`chesslab.engine_work` owns one append-only SQLite ledger for a study's engine
active wall-time allowance. It is separate from assignment counts and the V1
corpus ledger. Never reset an existing ledger or create a replacement to continue
past its cap. Missing/corrupt files and changed settlement receipts fail closed.

Create once with the prospective cap and a JSON provenance file:

```sh
python -m chesslab.engine_work create /absolute/private/engine-work.sqlite --seconds 7200 --metadata policy.json
python -m chesslab.engine_work reserve /absolute/private/engine-work.sqlite --identity unique-operation --seconds 20 --metadata operation.json
python -m chesslab.engine_work summary /absolute/private/engine-work.sqlite
```

Reserve the entire worst-case allowance before starting work. Concurrent
reservations are serialized; pending and interrupted work remains fully charged.
Import historical unmeasured operations as separately identified reservations
with their original evidence paths and conservative full charges. Such records
do not assert a live process or an observed duration.

After proving process exit, write a private receipt with `process_stopped: true`
and integer `active_ns`, plus the evidence for termination and measured segments.
Then settle through `settle(path, identity, active_ns, receipt=receipt_path)` or:

```sh
python -m chesslab.engine_work settle /absolute/private/engine-work.sqlite --identity unique-operation --active-ns 123456789 --receipt termination.json
```

The receipt and its hash remain part of subsequent verification. A settlement is
one-time, cannot exceed an unrecorded nominal charge silently, and never deletes
the reservation. An overrun is charged in full before raising `TimeoutError`;
inspect its cause before continuing. Over-cap totals block further reservations.
The ledger checks commitments and caller attestations, not OS process state.
The controller/auditor must verify the actual exit and enforce finite watchdogs.

For a one-shot evaluator, measure the entire startup/search/cleanup operation.
For the local game, sum private `engine_active_segment` journal events, recorded
with `monotonic_ns` around startup, each search (including failures), and cleanup
(including failed attempts). Do not substitute only the engine's reported search
time. The journal's legacy `opponent_returned.elapsed_seconds` includes other
controller timing and must not be charged a second time. Player/model idle waits
are outside active work. On abnormal shutdown, overlapping search/cleanup spans
may be charged twice conservatively; preserve this qualification. These are wall
durations, not CPU time, node counts, FLOPs, tokens or billing cost.

An unconfirmed engine exit retains the full reservation. The local game's worker
and owner-lease checks still apply. Freeze the updated environment runtime before
new games; these timing events cannot be retroactively added to old trajectories.

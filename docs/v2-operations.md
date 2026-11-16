# V2 launch and recovery

Read [RESEARCH_PLAN_V2.md](../RESEARCH_PLAN_V2.md) for the scientific contract.
This page describes mechanical controls; it records no capability result.

## Program-wide reservations

Create one private study ledger before the first subject assignment:

```sh
python3 -m chesslab.study_budget create evidence/private/v2/study-budget.sqlite
python3 -m chesslab.study_budget summary evidence/private/v2/study-budget.sqlite
```

The default limits come from the V2 plan. Creation refuses an existing path;
summary/reserve refuse a missing database. An interrupted or corrupt ledger must
be inspected, never silently recreated. Keep one canonical path in the checkpoint.
SQLite serializes concurrent reservations. Ordinary SQL updates/deletions and
additional limit rows are blocked; this is an operational guard, not protection
against a database owner replacing the file or dropping its triggers.

Reserve a unique identity **before** starting each actor/attempt. Use the Python
API from the controller, with metadata identifying its protocol, split and input
commitment. A pilot game consumes both `games` and `pilot_games`; a pilot diagnostic
consumes both `diagnostics` and `pilot_diagnostics`. The API rejects pilot-only
charges. For example:

```python
from pathlib import Path
from chesslab.study_budget import reserve

reserve(Path('evidence/private/v2/study-budget.sqlite'),
        'pilot-game-001', {'games': 1, 'pilot_games': 1},
        metadata={'purpose': 'pilot', 'protocol_sha256': 'actual-frozen-digest'})
```

Every player move-decision call, including invalid or missing responses, reserves
`move_decisions` separately. A diagnostic assignment is each independently
requested scored response; repeated memory probes consume additional diagnostic
units even when they use the same context. Reserve each new candidate policy once
before its first development assignment. Labels and new run IDs do not reset caps.
Keep failed and unused reservations: they are assigned work, not completed trials.
Any duplicate identity is rejected rather than charged twice or relaunched.

The ledger counts assignments, not execution time. Enforce actor clocks in the
delivery/collection adapter, independently verify actual start/end timestamps, and
keep engine-time and disk accounting alongside this ledger. Reserve worst-case
engine work before an operation and record actual work and overruns afterward.
The frozen M2 protocol owns final per-query limits and all stop rules.

## Player and controller channels

For diagnostic preparation or a history query, read
[V2 diagnostic construction and staged delivery](v2-diagnostics.md) before launch.
History exposure and query use the same actor with different file allowlists.

Use a fresh player context per game. The mechanical controller may supply a
screenshot and the visible turn/orientation, receive an intended move and perform
native coordinate input. Return only permitted visible feedback. Truth-state and
engine endpoints belong to the controller/evaluator; their existence does not
authorize player access. Audit actual tool calls and host model/effort metadata.

Before deriving coordinates, observe the current native window after focusing it.
The screenshot geometry can change with focus or fullscreen state. Preserve raw
screenshot bytes and detect the image format rather than assuming PNG from a file
suffix. An input return or changed image is insufficient proof of a chess move;
verify visible source/destination and promotion/terminal state.

## Frozen mechanics and interruption

Freeze the existing mechanical collector using `python3 -m chesslab.freeze` and
verify its manifest before play. Preserve the local environment's source/config
hashes separately; it is controller-side code and does not belong in the unaided
player's mechanical snapshot. Keep live imports independent of mutable checkouts.

The V2 task checkpoint points to `evidence/private/v2/progress.json`, the canonical
budget and active execution handles. On resume, inspect the actual host handles,
server process and browser before replacing an owner or sending another action.
A stale file, timeout or missing observation alone is not proof a subject stopped.
Preserve every attempt and error; follow the frozen recovery rule for the cohort.

V1's completion record and artifacts remain separate. Source-only PRs and merges
are authorized; study evidence, screenshots, model traces and paper outputs stay
under the repository's ignored private/artifact paths until publication approval.

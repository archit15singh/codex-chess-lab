# Codex Chess Lab

A research workspace for measuring chess decisions and browser reliability separately.
The scientific contract is [RESEARCH_PLAN.md](RESEARCH_PLAN.md). A functioning
collector or a bot win is not a strength estimate.

## Quick start

The evidence collector and its tests use only the Python standard library:

```sh
python3 -m unittest discover -s tests -v
python3 -m chesslab --help
python3 -m chesslab create my-run configs/feasibility.json
python3 -m chesslab export my-run
```

Use a new run ID for every game. Before running, replace unknown model metadata
only with independently observed values. Keep unknowns explicit. Configurations
freeze at creation; changes require a new run. Run exports contain private data
and remain under the ignored `evidence/private/` directory by default.

For post-game PGN verification only:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-evaluator.txt
```

## Boundaries and navigation

- [Protocol](docs/protocol.md): experimental controls, budgets and analysis.
- [Architecture](docs/architecture.md): small modules and evidence boundaries.
- [Milestones](docs/milestones.md): acceptance criteria and completion evidence.
- [Literature](docs/literature.md): primary sources; external findings are not ours.
- `configs/`: immutable run inputs; `chesslab/`: collection and descriptive stats.
- `tests/`: regression checks of the collector, never chess performance evidence.

Native Brave computer use is provided by the host, not a Python driver. The host
observes screenshots and executes coordinate clicks. The collector does not infer
positions, generate legal moves, control Brave, or enforce a host sandbox.
Review the full host trace in addition to the declared tool events. SQLite
triggers prevent ordinary record mutation but are not protection from a malicious
operator who owns the database. Evidence hashes require independent file readback.

## Research integrity

Use `purpose=feasibility` for integration runs. Pilot and held-out comparisons need
fresh, isolated player contexts and audited tool access. Engines and PGN libraries
belong in a separate post-game evaluator. Never supply evaluation answers to the
unaided player. Engine-assisted play is its own condition.

Raw screenshots, account state, permission records and study results stay local.
The requested source PR workflow does not authorize public research publication
or participant disclosure. Human play requires separate consent and permission.

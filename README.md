# Codex Chess Lab

A research workspace for measuring chess decisions and browser reliability separately.
The scientific contract is [RESEARCH_PLAN.md](RESEARCH_PLAN.md). A functioning
collector or a bot win is not a strength estimate.

## Quick start

The evidence collector and its tests use only the Python standard library:

```sh
python3 -m unittest discover -s tests -v
node --test tests/browser_collector.test.mjs
python3 -m chesslab --help
python3 -m chesslab create my-run configs/feasibility.json
python3 -m chesslab export my-run
```

Before live play, freeze collection mechanics and use that snapshot in the host:

```sh
python3 -m chesslab.freeze evidence/private/runtime-unique
python3 -m chesslab.freeze evidence/private/runtime-unique --check
```

The collector's `repo` and module import path must point inside the snapshot;
the private database and screenshot directory remain outside it. Code checkout
changes then cannot interrupt a live collector.

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
- [Native collector](docs/browser-collector.md): screenshot and guarded-click workflow.
- [Evaluator](docs/evaluator.md): strict PGN and optional bounded Stockfish analysis.
- [Paired analysis](docs/paired-analysis.md): family-level comparisons and missing-score coverage.
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

## Local evidence notebook

Use the separate reporting dependencies for local figures and the eventual paper:

```sh
.venv/bin/python -m pip install -r requirements-report.txt
.venv/bin/python -m chesslab.report path/to/evaluator.json \
  --purpose feasibility --output artifacts/research-notebook.html
```

The output is a self-contained dark notebook with an inline scientific figure and
an exact-value table. It retains finite-search inversions and missing/mate scores.
It is not a strength estimate or the final research package. Keep output local;
review it in Brave when no game owns the browser. CLI creation refuses to replace
an existing file; intentional notebook revisions may regenerate it after review.

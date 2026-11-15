# Offline evaluator

Run this only after play ends, in an evaluator environment isolated from every
unaided player. The collector itself needs no chess dependency.

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-evaluator.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m chesslab.evaluate evidence/private/game.pgn \
  --output evidence/private/game-validation-v1.json \
  --actions evidence/private/game-actions.jsonl \
  --require-board-terminal
```

The CLI reads exactly one standard-chess mainline. It requires an explicit Result
header and a matching final movetext result, rejects illegal/null moves and ignored
junk, and caps games at 400 plies. Comments and numeric annotations are accepted;
variations and multiple games are rejected explicitly. FEN starts require SetUp=1
and a structurally valid board. Structural validity is not proof of historical
reachability. Missing or ambiguous SAN fails rather than silently repairing it.

Automatic board endings must agree with the declared result. A resignation,
timeout, agreed draw, or other non-board ending remains a header-only claim until
independent UI evidence verifies it. `--require-board-terminal` rejects such claims;
without it the output marks `board_terminal=false` and `board_result=null`.
No rating is estimated. Only referenced screenshots are byte-verified; missing
references and visual meaning require a separate audit. Paths are relative to the
actions file and must resolve inside its evidence directory, including symlinks.

## Optional Stockfish analysis

Install Stockfish separately from its official distribution or a trusted package
manager. This repository does not bundle an engine binary.

```sh
.venv/bin/python -m chesslab.evaluate evidence/private/game.pgn \
  --output evidence/private/game-engine-v1.json \
  --engine /opt/homebrew/bin/stockfish --nodes 10000 --hash-mb 16 \
  --timeout 30 --total-timeout 600
```

Every ply gets two searches from the identical pre-move board: an unrestricted
best-move search, then a search constrained to the selected move. Each receives
the same node limit. A fresh game identity and explicit hash clearing prevent
transposition-table carryover between searches. Threads=1 and fixed Hash are
required; full strength and empty tablebase path are set when those options exist.
The report preserves engine identity, binary checksum, option defaults, configured
options, node/depth/time observations, and limits. External network assets are not
independently hashed; use the bundled networks for reproducibility.

Both scores use the moving side's perspective. Mate distances remain separate
from centipawns. Raw centipawn differences can be negative due to finite-search
variance; the report retains these inversions alongside a clipped descriptive
loss. Bounded score outputs yield no numerical loss. These approximate engine
scores do not measure a model's human competitive rating. Actual search nodes may
slightly exceed a nominal node limit; retain the observed counts.

The async watchdog bounds each engine operation, with a separate total analysis
watchdog. Shutdown gets at most five additional seconds; the transport closes on
failure. A failed or timed-out analysis exits nonzero and writes no success file.
Output creation is exclusive so prior evidence and source PGNs are not replaced.

## Sources and limitations

The integration follows the official [python-chess engine API](https://python-chess.readthedocs.io/en/latest/engine.html),
including root-move restrictions, score perspectives and node limits. The
[Stockfish developer guidance](https://official-stockfish.github.io/docs/stockfish-wiki/Developers.html)
describes UCI search limits and process separation; [Stockfish terminology](https://official-stockfish.github.io/docs/stockfish-wiki/Terminology.html)
explains transposition memory. Sources inspected 2026-11-15. These docs support the
API implementation, not a claim that any experiment has already been run.

All evaluator tests use synthetic fixtures or mocks and are engineering evidence.
The no-chess standard-library test environment explicitly skips evaluator tests;
run the dedicated evaluator environment to exercise them. No browser capture,
model identification, tool-use compliance, consent, or screenshot interpretation
is established by a legal PGN or a matching file checksum.

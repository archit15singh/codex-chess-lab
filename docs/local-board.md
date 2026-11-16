# Controlled local chess board

`chesslab.local_board` provides one loopback-only, screenshot-and-coordinate chess
game. It is an engineering environment, not evidence of model chess strength.
No browser or model is launched by the module. Its only nonstandard dependency is
`chess==1.11.2` from `requirements-evaluator.txt`; the baseline collector remains
independent of that dependency.

The frozen start FEN defines the initial rule state and counters. Repetition
history begins there; earlier moves are not reconstructed from a FEN. A study
requiring prior opening history must start at the initial board and replay it or
add a separately reviewed, prospectively frozen prefix mechanism.

The player opens `http://127.0.0.1:8765/` in native Brave, observes the rendered
board, then clicks a source and destination square. Ranks/files remain outside the
board image, whose square geometry is exactly an 8-by-8 grid. The image reserves
its aspect ratio before loading. Responsive resizing or focusing a native window
can still change screenshot coordinates: reobserve the actual window before any
uncertain click or retry. No DOM-based adapter is provided or authorized here.

Choose promotion (queen, rook, bishop or knight) before the second click. Castling
uses the king's source/destination squares. The ordinary Claim draw button claims
an existing threefold/fifty-move draw. To announce a qualifying next move without
playing it, select Claim with next move and click both squares. Automatic
fivefold/75-move, stalemate, insufficient material and checkmate use python-chess
rules. Resignation is explicit. A decision/wall timeout or opponent failure ends
with result `*`; it is a harness outcome, not an invented board loss.

## Freeze configuration without starting clocks

Use an evaluator Python interpreter outside the frozen player context. For
example, in a checkout with an existing `.venv`:

```sh
.venv/bin/python -m chesslab.local_board create evidence/private/v2/board-fixture-001 --config fixture-config.json
```

These commands are engineering fixtures. Scientific collection must use a verified
mechanics snapshot under the repository freeze workflow, not this mutable checkout.

The following full configuration is a manual fixture. Save it as
`fixture-config.json` outside a subject's allowlist:

```json
{
  "mode": "manual_fixture",
  "start_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "player_color": "white",
  "orientation": "white",
  "decision_seconds": 90,
  "wall_seconds": 3600,
  "engine": null
}
```

`create` refuses an existing directory, validates a standard legal FEN and freezes
config/source SHA-256. It writes a private controller token but starts no game,
clock, engine, actor or browser. Fixtures must be identified as synthetic in the
experiment ledger and consume no model-capability denominator by themselves.

For a controlled opponent, set `mode` to `controlled` and replace `engine` with:

```json
{
  "path": "/absolute/path/to/stockfish",
  "options": {"Threads": 1, "Hash": 16, "SyzygyPath": "", "UCI_LimitStrength": false},
  "nodes": 2000,
  "movetime_ms": null,
  "timeout_seconds": 10
}
```

This is an engineering example, not a V2 scientific budget or opponent rating.
Use exactly one positive node or millisecond budget. A movetime must not exceed
`timeout_seconds * 1000`; python-chess's transport allowance can add the configured
timeout to a timed search. The binary and any explicitly configured `EvalFile*`
network files are hashed. Embedded networks are covered by the binary hash.
Other external engine assets/tablebases are not inventoried: leave tablebases
empty and separately freeze any additional assets before a scientific run.
Engine identity, UCI option defaults, requested options and per-query basic work
statistics/elapsed time are private records. No PV, evaluation or recommendation
is sent to the player. Freeze/calibrate actual opponent settings before subjects;
a configured engine Elo is not a measured Codex rating.

## Start the prepared game

```sh
.venv/bin/python -m chesslab.local_board serve evidence/private/v2/board-fixture-001 --port 8765
```

`serve` takes a cooperative host-wide owner lease, binds only `127.0.0.1`, then
verifies frozen source/config/binary files and opens game clocks after successful
engine initialization. It prints the player URL and token **file path**, never the
token. It starts the opponent immediately if the player is Black. Port `0` picks
an available loopback port for integration fixtures. Only one game owns this
server/process and one cooperative lease may exist per OS user, even on different
ports. This is not an OS-level exclusion of other browsers/programs.

The first decision clock starts at `game_started`, before browser loading; each
subsequent player clock starts when the opponent move is committed. Invalid moves
and page reloads do not reset clocks. Equality to a limit is expired. A background
service tick checks wall/player deadlines even without HTTP requests. An ended
game closes the opponent process; a late engine result never changes its board.
A decision limit rejects late actions, rather than interrupting an independent
host model turn. The external controller must still prove actual actor completion.

Starting a prepared run creates `events.jsonl` exclusively. A second serve of that
run is refused, including after a partial failure. There is no resume/reset or
subject retry interface. Ctrl-C records an operator stop, closes the engine and
releases the process's own lease only after its worker has actually ended. If
shutdown cannot observe the actual engine process returncode or prove move-worker
termination within its bounded two-second checks, it records
`shutdown_blocked`, leaves the journal open, raises an error and preserves the
lease. Failed/interrupted engine initialization with no confirmed process handle
also preserves that lease. HTTP handlers have five-second socket timeouts and
are drained before owner release; a closed game accepts no further evidence
writes. A crash may also leave the lease in the OS temporary
directory (`codex-chess-local-board-<uid>.lock`): preserve its owner metadata and
prove the original owner ended before an operator removes it. Never steal a lease
or delete a failed run to retry the same assignment.

## Information and evidence roles

Player routes are `/`, `/view`, `/board.svg` and POST `/action`. They expose only
the board's visible occupancy, orientation labels, normal rules rejection, turn,
clock/status and result. There is no FEN, PGN, legal-move list, hidden board-state
JSON, engine config or evaluation in these responses. Rendered piece shapes do
encode visible occupancy; DOM/file/network inspection remains prohibited by the
player's tool contract. This service is not a sandbox against arbitrary local
filesystem or programmatic access.

`GET /controller/state` requires `X-Controller-Token` read from the private token
file. Its full FEN/move history is for controller verification only. Authenticated
`POST /controller/action` permits moves on either side **only in manual fixtures**;
it is disabled for controlled opponents. The token is not embedded in HTML or
URLs. Browser actions require the exact loopback Origin/Host and bounded JSON;
no CORS or arbitrary file-serving route exists. Each submitted action carries a
fresh `intent_id` and expected board `version`. Used identities, stale versions,
out-of-turn moves and illegal moves cannot be replayed to mutate the board.

The private directory contains frozen files, append-only hash-linked events and
an atomic current-state checkpoint. Intent is logged before applying a move, then
an application/terminal event and state are persisted; failed attempts remain.
A failed `.part` state write remains for diagnosis. These records are controller
owned, not player attachments. Native screenshots/click traces and host model,
effort and actual turn-completion proofs must be collected separately by the
existing host controller and linked to these versions/events. Defaults in a model
config are not proof of actual host settings.

Do not expose this directory or controller token to the player. Root's frozen V2
protocol owns assignment IDs, screenshot evidence, model effort, source snapshots,
aggregate model/engine/disk budgets, scientific stopping rules and scoring. This
module supplies a game mechanism and records, not a subject dispatcher or scorer.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_local_board.py' -v
.venv/bin/python -m unittest discover -s tests -v
```

Tests use temporary positions and a fake opponent seam. They cover actual HTTP
routing, Origin/Host/token guards, legal transitions, promotions, castling,
en passant, repetition/draws, terminal/no-move positions, exact deadline boundaries,
late engine suppression, config tampering, exclusive runs and owner leases. They
start no browser, real engine, model or subject. A native Brave observation/action
preflight and independent trajectory audit are still required before M1 can be
accepted as an experimental milestone.

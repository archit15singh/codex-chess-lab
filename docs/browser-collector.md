# Native browser evidence collector

`scripts/browser_collector.mjs` wraps the host's native CUA binding. It does not
launch a browser, inspect page internals, reconstruct a board or choose a move.
The only child process is the local Python evidence CLI, invoked without a shell.
All UI actions go through the injected CUA binding.

Import it in the host CUA JavaScript runtime after selecting the native Brave app:

```js
var module = await import('file:///absolute/repo/scripts/browser_collector.mjs');
var collector = module.makeCollector({
  target: brave, repo: '/absolute/repo',
  db: '/absolute/repo/evidence/private/runs.sqlite', run: 'unique-run-id',
  python: '/absolute/path/to/python3',
  directory: '/absolute/repo/evidence/private/unique-run-id'
});
// A unique ?revision=<source-sha> import suffix avoids stale host module caches.
collector.provenance();
await collector.observe();
```

Choose a move visually, then call `collector.move({actionId, move, from, to})`.
Coordinates refer to the current native screenshot. The helper stores the decision
observation, saves another pre-click image, reserves the intent in SQLite, records
the input capability, and executes two native clicks. It discards the host-required
post-action accessibility refresh and emits a saved screenshot. It does not decide
whether a move succeeded. After inspecting that image, call
`collector.verify({actionId, outcome:'executed', note:'visible source/destination'})`.
Use `not_executed` only when a new observation establishes that the action failed;
use `uncertain` to preserve uncertainty without releasing the reservation. Each
verification consumes its image; observe again before resolving uncertainty or
selecting a new move. Public recovery/verification calls are rejected while native
execution is in flight. A failed
click also leaves its reservation pending. Observe again before recovery.

The next move is rejected while any intent is unresolved, including after runtime
restart. A persistent exclusive owner file under the database directory blocks
a second helper for the same run, including across processes. `collector.close()`
releases ownership only after native execution has returned, disables the old
helper and leaves any unresolved ledger action intact. A replacement must observe
and resolve that action before moving. Terminal recording releases ownership.
After a crash, preserve the owner file until the old execution handle is confirmed
terminal or missing; only then may the controller remove that exact stale owner
file. PID, elapsed time and the lock file alone are not termination evidence.
Never automatically expire or steal ownership. Every evidence-bearing CLI append reads the actual screenshot bytes and
records the digest and path. Keep files local and validate their hashes again in
post-game audit. Clock/animation changes may alter screenshots; a changed image
alone never proves a successful move.

At a visibly verified game ending, call
`collector.terminal({result:'win'|'loss'|'draw'|'aborted',note})`. This closes the
run; export with `python -m chesslab export <id>`. Terminal results, permissions,
model identities and host-tool compliance remain independently auditable claims.
Provenance records the collector source hash computed when the module is imported.
Use a unique revision import suffix when changing versions; freeze that version
for each run. This helper provides transaction guards, not a tool sandbox.

Tests use synthetic bytes and fake input targets; `node --test
 tests/browser_collector.test.mjs` tests failure recovery without playing chess.
A native screenshot-only smoke test must also pass in the host before pilot use.

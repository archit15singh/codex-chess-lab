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
  directory: '/absolute/repo/evidence/private/unique-run-id',
  deadline: '2030-01-01T00:20:00Z', // replace with this run's actual frozen ISO deadline
  maxAttempts: 200
});
// A unique ?revision=<source-sha> import suffix avoids stale host module caches.
collector.provenance();
await collector.observe();
```

The optional ISO deadline prevents starting a new move at/after that time; the
attempt cap counts all reserved intents, including rejected choices. An already
started native sequence and final observation may finish after the deadline.
Settings are recorded once in an immutable ledger observation before the first
move. A replacement helper adopts those settings if omitted and rejects attempts
to change them. Record actual timing; this is not a guarantee of instant task
preemption. Budget
errors preserve evidence and require observation/stop, never an automatic retry.

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

For a visible promotion chooser, use `collector.promote({actionId, at})` to
continue the same pending UCI intent (for example `d7d8q`). Choose the square of
the already declared piece from the screenshot. The helper records a durable
reservation before one click, never repeats the source/destination clicks, and
requires visual verification afterward. It rejects a second promotion click,
including after restart. It does not identify the chooser or recommend a piece.

If collection cannot continue, observe and call
`collector.halt({reason, note})`. This records a harness stop and preserves any
unresolved action without claiming a chess outcome. A stopped run can be observed
but cannot accept further moves, promotion input, verification or terminal results.
Record later platform outcomes or controller recovery in separate follow-up
evidence or a separate diagnostic run. Analysis rejects a ledger containing both
a harness stop and a terminal result. This is a collection guard, not protection
against direct database or CLI misuse.

The next move is rejected while any intent is unresolved, including after runtime
restart. A persistent exclusive owner file under the database directory blocks
a second helper for the same run, including across processes. `collector.close()`
releases ownership only after native execution has returned, disables the old
helper and leaves any unresolved ledger action intact. A replacement must observe
and resolve that action before moving. Terminal recording releases ownership.
After a crash, preserve the owner file until the old execution handle is confirmed
terminal or missing; only then may the controller remove that exact stale owner
file. PID, elapsed time and the lock file alone are not termination evidence.
Never automatically expire or steal ownership. Evidence-bearing CLI appends using
`--artifact` read the actual screenshot bytes and record the digest and path.
Keep files local and validate their hashes again in
post-game audit. Clock/animation changes may alter screenshots; a changed image
alone never proves a successful move.

When a fresh post-action image visibly establishes both the pending action's
outcome and the game ending, call the bookkeeping-only helper **before** calling
`verify` separately:

```js
collector.finish({
  actionId, outcome: 'executed', // or 'not_executed'; never 'uncertain'
  result: 'win', // 'win', 'loss', 'draw' or 'aborted', as visually confirmed
  note: 'Describe the visible action outcome and terminal UI'
});
```

`finish` requires the active owner, no native execution in flight, no harness stop
and an unconsumed observation. It validates outcome and result before appending,
checks the saved file against its source observation digest, and calls the normal
verification path, including its matching pending-action guard. It then checks
that verification's path, digest and `observed_at` against the source observation
and appends a terminal event with that same binding. It closes ownership after
success. It makes no screenshot, accessibility or input calls, so it can complete
ledger bookkeeping after the host's UI completion summary. The caller must first
inspect the terminal image; the collector does not infer checkmate or any result.

These are two separate appends, **not an atomic transaction**. If verification
succeeds and a later step fails, that verification remains recorded, its pending
action is resolved, its observation is consumed, and ownership stays held until
explicitly closed. Inspect the exported ledger before recovery: a terminal append
may have committed even if its process reported an error. Do not repeat the action
or pretend both appends failed. If closure is still needed, use a new observation
with `terminal`, or preserve the existing immutable image and its checked binding
in separately audited controller recovery evidence. `finish` cannot reuse a
consumed image. The terminal event copies the checked verification binding rather
than reading the file again; preserve screenshot files unchanged throughout this
procedure and audit their hashes afterward. This is a procedural immutability
requirement, not an operating-system guarantee against external file changes.

`observed_at` is assigned after screenshot bytes return and the file is saved. It
is the collector's observation timestamp, not a measured pixel capture time or
the later verification/terminal append time; both events retain that same value.

For a terminal UI with no pending action, observe and call
`collector.terminal({result:'win'|'loss'|'draw'|'aborted',note})`. If you already
called `verify`, it consumed the image, so this path requires another observation.
An unresolved action still blocks `terminal`. This closes the run; export with
`python -m chesslab export <id>`. Terminal results, permissions,
model identities and host-tool compliance remain independently auditable claims.
Provenance records the collector source hash computed when the module is imported.
Use a unique revision import suffix when changing versions; freeze that version
for each run. This helper provides transaction guards, not a tool sandbox.

Tests use synthetic bytes and fake input targets; `node --test
 tests/browser_collector.test.mjs` tests failure recovery without playing chess.
A native screenshot-only smoke test must also pass in the host before pilot use.

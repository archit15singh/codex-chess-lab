# Post-response position scoring

`chesslab.position_score` is private evaluator tooling. Run it only after the
controller independently verifies that the actor handle is authoritatively
completed. Never give its files, output directory or answers to the player.
The completion flag and hashed controller evidence artifact are an operator gate;
this module cannot authenticate host status or establish a tool sandbox.

```sh
.venv/bin/python -m chesslab.position_score <private-trial-directory> \
  --output <new-private-score-directory> \
  --engine /absolute/path/to/pinned/stockfish \
  --actor-completed \
  --completion-evidence <controller-completion-evidence-file>
```

The output parent must already exist. Use exactly one declared scoring destination
per trial. The command reserves that directory exclusively before processing or
engine work. Existing destinations, including partial failed attempts, are
refused. Do not choose another directory to retry a failed reference or obtain a
more favorable score. No actors, orchestration, browser interaction or automatic
retry are implemented. The isolated `requirements-corpus.txt` environment already
supplies the dependencies. The CLI prints only the output path, digest and quality
status; detailed private answers remain in files.

## Evidence checks and outcomes

Inputs are the trial manifest, launch record, optional initial/final submission
records, sealed corpus item, player image/common-rules bundle and frozen treatment
attachment. Prepared-input hashes and the trial-manifest launch commitment must
match. The scorer records source hashes for itself, the existing evaluator,
trial mechanics, corpus metadata helper and budget guard. It rechecks input and
source hashes before and after reference work, including the absence of missing
submission files. Settings in the trial manifest remain *desired* settings;
independent host model/effort readback and channel audit are still required.

Only the requested item is scored. Its paths must stay inside the corpus, its
image/player/item files must match the sealed corpus hashes, occupancy/common
rules must agree with its FEN, and retained generated history must legally replay
to the snapshot. This checks source consistency; it does not prove that a player
saw the image or obeyed its assigned capabilities. The controller still owns
held-out protection and must not expose final outcomes before lesson freezing.

Each saved submission is checked against its exact raw base64 bytes and SHA-256.
Duplicate JSON keys and nonfinite values are rejected; parsed responses must
match raw validation. Recorded lateness and assigned boolean legality feedback
are independently recomputed. Bad evidence wrappers are `invalid_record`, while
properly preserved malformed actor JSON is `malformed_response`. Both remain
visible. Invalid evidence wrappers prevent a qualified deadline success and
reference scoring; they are not silently repaired into player outcomes.

Initial and final outcomes separately retain presence, format validity, legality,
lateness, dispatch-to-record latency, move, confidence, square transcription and
common-rules fidelity where defined. Same-square proposals are illegal choices.
Unknown square/rules answers remain wrong/unknown, not missing observations.
Square exactness concerns occupancy only. Castling rights, side-to-move and legal
en-passant availability measure fidelity to the common rules banner; halfmove
clock is not requested by the response schema and is not claimed as a measured
response outcome. Preparation duration, preparation-to-dispatch delay and
initial-to-final revision time are recorded separately.

`attempted_trials` is one even when no response exists. `deadline_success` requires
a valid final response, legal move, consistent evidence and a record strictly
before the frozen deadline. It does not depend on whether engine scoring succeeds.
A legal late choice may receive reference analysis, explicitly marked secondary;
it never becomes an on-time success. No response is replaced by an earlier valid
proposal, and no failed trial is removed from coverage denominators.

## Reference policy and snapshot semantics

Only a valid legal final choice with consistent evidence invokes the existing
`evaluate.evaluate`. Its binary must match the corpus-pinned SHA-256. A private
one-ply PGN includes explicit SetUp/FEN headers, the selected move and matching
board result when that move ends the board; other results are `*`.

The root is the **FEN snapshot**, including turn, castling, legal en-passant state
and halfmove/fullmove counters. Source history is retained and hashed for
provenance, but is not supplied as prior repetition history to the engine. This
matches the assistance arm's `chess.Board(fen)` semantics. The study is not a
repetition-claim task and does not measure whole-game value; a later history-aware
study would require a separately frozen treatment/reference policy.

The controller's private amendment records the actual clarification timing:
after three A-arm training responses were collected, before any reference
scoring, lesson generation or final testing. At that point the controller had
seen stage/format/timing reports, with no chosen moves, piece maps or quality
answers exposed. This was a prospective pre-reference clarification, not a
preregistration before all training actors. The study remains exploratory.
This source records repetition-claim and whole-game-value assessment as false.

The reused evaluator performs two independent 100,000-node searches from the
same pre-move root and moving-side perspective: unrestricted best versus selected
root move. It uses Threads=1, Hash=16 MiB and resets hash/fresh game identity for
each search. Actual node overshoot, PVs, scores, bounds, engine identity/defaults
and configured options remain in the private evaluation record. Operation timeout
is 3 seconds; total evaluator work is bounded at 10 seconds, with cleanup at most
3 additional seconds. The entire evaluator call, including startup and cleanup,
runs inside a 13-second `engine_allowance`, drawing on the same 1,800-second
study budget already charged for generation and assistance. A timeout, overrun or
insufficient budget is a preserved scoring failure, not permission to lower nodes
or retry.

Finite exact centipawn differences retain negative search inversions. Their
nonnegative clipping is descriptive and separately named. Mate, bounded and
missing scores retain separate unavailability reasons; no numeric centipawn loss
is invented. Primary 200-cp and sensitivity 100/300-cp threshold indicators have
values only on the exact-score coverage set. Best-move agreement is diagnostic;
multiple equivalent moves can make exact UCI agreement uninformative. No rating,
full-game strength or causal claim is produced by this scorer.

## Output and failure coverage

| Artifact | Purpose |
| --- | --- |
| `inputs.json` | Trial/source/completion-evidence hashes and operator attestation |
| `corpus-inputs.json` | Hashes of the selected item's sealed input sources |
| `measurements.json` | Attempt, initial/final reliability/perception/rules/timing outcomes before reference work |
| `reference.pgn` | Eligible final choice and private snapshot root only |
| `evaluation.json` | Successful existing-evaluator raw output |
| `score.json` | Completed measurement plus qualified quality summary, or explicit ineligibility |
| `failure.json` | Failed scoring attempt, input hashes and error, with no automatic retry |

Reference failure leaves `measurements.json` and `failure.json`; it can therefore
have an on-time legal response but no engine-score coverage. Input-integrity
failure can occur before measurements are trustworthy and still leaves the
attempt/failure and raw input hashes. Analyses must enumerate every declared
scoring destination and include failures, not collect only `score.json` files.
Keep the original trial records and failure directory for independent audit.

Tests use temporary synthetic corpus/trial files, mock reference evaluation and
public starting-board or Fool's Mate examples. They do not read study positions,
launch actors, run a real engine, or establish any Codex chess result.

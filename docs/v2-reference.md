# Bounded V2 reference searches

`chesslab.v2_reference` runs one evaluator-owned operation from a private JSON
request. Freeze its settings in the study protocol before final collection. The
module does not select an appropriate reference budget or prove subject
completion; the controller must establish those gates separately. Search help is
another condition with its own declared input and budget, never an unaided tool.

The request has exactly `engine` (executable path), `fen`, positive integer
`nodes`, integer `timeout_seconds` from 1 through 30, and `selected_move` (legal
UCI or null). A null selection performs one unrestricted search. A legal selection
performs an unrestricted and a restricted-root search at the identical snapshot.

```sh
python -m chesslab.v2_reference private-request.json /absolute/private/unique-output --budget /absolute/private/engine-work.sqlite --identity unique-reference-operation
```

An operation reserves its full startup/commands/cleanup allowance in the shared
engine-work ledger. Every engine wait has a deadline; cleanup closes the
transport and requires an actual process returncode. Commands are shielded from
timeout cancellation until transport cleanup, then drained. This avoids leaving
the library's analysis-completion future canceled before its process-exit callback.
Unconfirmed exit keeps the full allowance and raises: inspect the actual process
before any subsequent engine work. Failures preserve their request, source hashes
and result; neither output reuse nor automatic retries are supported.

Each operation starts a fresh full-strength Stockfish process with one thread,
16 MiB hash, strength limiting off and no tablebases. Clear Hash and a fresh game
identity precede each search. Keep the binary hash, effective network provenance,
software versions and private output with the package. The module records
advertised network defaults; it does not independently hash embedded network
bytes or establish which external network was loaded. Verify that provenance
separately before collection.

The reference root is a full-FEN snapshot. It does not reconstruct earlier
repetition history. Report exact snapshot agreement, CP, mate, bounds, PV, depth,
requested/actual nodes, engine-reported time and measured active wall time. A CP
difference is available only when both same-side scores are finite non-mate,
unbounded values. Negative differences remain explicit finite-search inversions;
do not clamp them into apparent perfect moves. Mate/bound/missing scores stay
unavailable for CP comparisons. An engine recommendation is a bounded-search
output, not proof of the globally best move or a human rating.

For comparisons across arms, choose and hash a common reference per task before
computing agreement; do not give each condition a selectively deeper reference.
Preserve selected-move analysis coverage, missingness and timing even when it
cannot enter a common CP cohort. Actual node counts can overshoot nominal UCI
limits. Active wall time, nodes, model tokens and billing cost are distinct.

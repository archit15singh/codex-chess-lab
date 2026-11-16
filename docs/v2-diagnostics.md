# V2 diagnostic stimulus construction

`chesslab.v2_corpus` builds inputs from an explicit private specification of legal
move histories. It runs no model or engine. It is controller/evaluator software;
never put it or its truth directory in an unaided player's allowlist.

```sh
.venv/bin/python -m chesslab.v2_corpus evidence/private/v2/pilot-stimuli-unique --spec private-spec.json
.venv/bin/python -m chesslab.v2_corpus evidence/private/v2/pilot-stimuli-unique --check
```

Creation refuses an existing directory. A generation failure preserves partial
files and a failure record. Verification checks the exact file inventory, hashes,
source-specification commitment and legal-history/task constraints. Commit the
manifest digest in the assignment protocol before subject collection; an owner
can otherwise replace files and their manifest. These checks do not prove model
performance or provide a sandbox.

## Input interface

The specification has exactly `schema_version: 2`, `cases` and
`excluded_position_sha256`. Each case supplies `id`, `family`, `split`, `task`,
`moves`, `orientation` and `style`. Identities use lowercase letters, numbers,
underscores or hyphens. Splits are `pilot`, `training`, `development` and `final`.
Supply the study's actual sampled histories and seeds in private files; public
source contains no final benchmark positions or fixed generation seed.

`moves` is a legal standard-chess UCI history from the initial board. The builder
checks every transition and rejects continuation after an automatic ending.
The final state is the observed task. Tasks are:

- `perception`: transcription and separately declared move consequences.
- `move`: a decision task for reasoning, search or policy comparisons.
- `correction`: adds `proposal`, a coordinate-UCI move independently verified to be
  illegal in that position. Treatment delivery may reveal the fixed rejection
  text; the control does not receive it. The proposal is externally injected,
  never an observed spontaneous player error.
- `history`: adds ordered observed `frames` (ply numbers including the final
  frame), a prior `query_ply`, `query_squares`, and `alternative_moves`.

A history task must supply a constructive ambiguity witness: the alternative
legal history has the same length and identical full final FEN, but different
answers at the queried past checkpoint. That checkpoint must be among the shown
frames and precede the final observation. Thus neither current occupancy nor
current rule metadata uniquely determines the target. Include balanced witnesses
and target baserates in the protocol; the validator alone does not establish a
representative or difficult memory task.

## Splits and prior-benchmark exclusions

Each named source family belongs to one split. Every exposed and scored position
is registered against family/split identities, including nonqueried history
frames. Only a history's literal ply-zero initial setup frame is exempt from that
cross-split registry; scored states are never exempt. Repeated renderings within a family
remain dependent observations. The builder checks rendered and scored states
against the supplied prior-benchmark exclusion hashes, using the first four
legal-en-passant FEN fields. Construct those hashes offline from the previous
study's reserved task states without sending its items or answers to new players.

The protocol must distinguish unavoidable common setup positions from reused task
instances, review ancestry and transpositions, and declare grouping before final
collection. Different labels do not manufacture independent families. The input
validator cannot infer all semantic ancestry or pretraining exposure.

## Player files and truth

`player/<id>.json` is a controller delivery manifest containing the observation image, orientation, task and explicit
common rule metadata. This supplied metadata is diagnostic assistance; such an
assignment is distinct from a screenshot-only full browser game. History files
also reference the assigned frame sequence and question. A history manifest is
not a direct player query packet: delivering the entire manifest at query time
permits readout and does not qualify as retention. Correction files give
the fixed proposal. Deliver each condition's exact file allowlist, not the whole
corpus directory.

`evaluator/cases.json` retains board truth, full histories, source groups, memory
answers, ambiguity witnesses and validated history records. A state/history
treatment may receive a prospectively selected attachment from that truth; an
unaided condition may not. Current-state transcripts and validated history have
different information benefits and must remain separately labelled.

`plain`, `compact`, `angled` and `clutter` are deterministic vector renderings.
Compact reduces pixel resolution; angled rotates the board seven degrees;
clutter uses a second board theme and surrounding UI panels that cover no board
squares. All omit last-move, check and arrow hints. These transformations create
challenge distributions, not a guarantee that a model will make errors. Inspect
actual images and use pilot evidence before freezing difficulty and sample size.
Keep PNG bytes, SVG commitments, software versions and exact-value truth together.

This module builds stimuli only. Assignment budgets, randomized arm order,
response clocks, actual host-tool/model audits, held-out selection, reference
evaluation, statistics and paper claims remain the study controller's duties.

## Mechanical response delivery

`chesslab.diagnostic_trial` is a separate standard-library-only module. Its
`prepare(directory, config, images)` interface copies an explicit image allowlist,
writes a player input packet and freezes file/source commitments. The config
declares task, purpose, condition, desired model/effort, response seconds and
context. History preparation additionally requires `image_plies`, the ordered
checkpoint number for each image; the packets preserve those labels so a past
query cannot be confused with an image's list index. Common diagnostic context is orientation and rule metadata; history and
correction tasks also require their query or fixed initial proposal. State,
history, rejection, search and candidate/sham attachments are accepted only in
their declared condition. The module checks structure, not chess truth.

For history, preparation writes two packets. `exposure.json` contains only past
frames and orientation, with no question or final frame. The fresh actor may open
only those assigned files during exposure, then replies READY. After verifying
actual host completion, the controller calls `record_exposure(directory,
actor_thread_id, completed_turn_id, evidence_file)` to pin an immutable host-proof
snapshot. This is a controller attestation; the separate host audit must verify
the proof, observed file accesses and original actor identity.

The same actor receives `input.json` in a later query turn. It contains only the
current image, question and common metadata, plus a historical record in the
assigned external-history condition. Old image paths are outside the query-turn
allowlist: retaining earlier multimodal context is permitted, reopening past
files is not. Audit calls by phase. A fresh replacement context or past-file
reinspection invalidates the specified memory contrast. Each scored query is one
diagnostic assignment; include unscored exposure turns in resource accounting.

Before the query dispatch, reserve the canonical program budget and call `launch`:

```sh
python -m chesslab.diagnostic_trial launch /absolute/private/trial
```

History launch additionally requires `--actor-thread-id <original-id>`. It refuses
a missing exposure receipt, changed proof or different actor identifier. Exposure
and query packets together do not enforce a filesystem/tool sandbox; those access
restrictions require actual trace checks before making a memory claim.

The move/perception/correction player, or the history actor's query turn, receives only `input.json`, its exact image paths and the frozen
submission command. It submits one JSON object through quoted stdin to
`python -m chesslab.diagnostic_trial submit /absolute/private/trial`. Use a frozen
mechanical runtime containing this module and `chesslab/__init__.py`, with absolute
Python/runtime paths; it imports no chess library or evaluator. Parent notification
can be delayed, so the response is timestamped at this direct submission rather
than when the controller eventually reads it. Report host completion and parent
receipt separately; submission is not proof the actor actually stopped.

Response shapes are `{"move":"<UCI>"}` for move/correction,
`{"move":"<UCI>","piece_map":{...}}` for perception (all 64 squares), and
`{"recall":{...}}` for the exact queried history squares. Use standard uppercase
White/lowercase Black symbols, `.` for empty and `?` for unknown. Unknown values
remain responses and require explicit accuracy treatment in the frozen scorer.
Syntactically valid UCI is not a legality judgment.

Only one launch and one response file may be created. Equality to the deadline
is late; input/source mutation or an altered clock duration fails closed. Malformed
bounded response bytes remain base64-encoded with a digest, without strategic
feedback or automatic retries. A source fix cannot be deployed into a live frozen
trial. The parent must audit actual host settings, allowed tools, exact delivered
inputs, original timing and termination before the separate evaluator reads truth.

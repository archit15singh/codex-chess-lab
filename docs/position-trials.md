# Supplementary position trials

This offline module supports the private prospective matched-position study. It
does not operate Brave, measure full-game reliability, or estimate a chess rating.
Its image-plus-common-rules control is separate from the screenshot-decision
Duolingo baseline. Corpus generation and all evaluator files stay outside player
contexts; see [corpus.md](corpus.md).

The controller prepares one trial immediately before launching one fresh actor:

```sh
.venv/bin/python -m chesslab.position_trial prepare private/corpus p001 A private/trial
```

Use a new directory for each trial. The preparation result is controller-only:
its manifest links evaluator sources and must not be given to the actor. Supply
only its named player JSON, image, `attachment.json`, neutral brief and submission
commands. Never supply a corpus directory listing or the evaluator/source files.
The immutable manifest records source hashes, desired model/effort and preparation
times. Immediately before dispatch, the controller runs `launch private/trial`
to record a90-second final-submission deadline. Preparation and engine assistance
precede that clock. Host dispatch/startup consumes the actor budget;
read back actual model/settings and audit the tool trace independently.

Arms A/B/H/I receive no legality feedback. C/D/E/F/G receive one initial boolean
verdict, never a legal-move list or explanation. B/D/E/F/G have exact occupancy;
E requests low effort; F chooses high iff in check, at most10legal moves, or at
most12pieces. Otherwise F requests low. G additionally requires `--engine` and
records a2,000-node single-thread Stockfish recommendation; its preparation time
and actual node count remain separate from the actor budget. H/I require the
frozen lesson or word-matched sham via `--supplement`. Every arm gets one initial
submission and one final revision opportunity, with the same deadline.
The search operation reserves the trial directory before engine work and uses
the shared study budget initialized from corpus-generation work. Failed/crashed
preparations remain records; they are not silently repeated. Engine query/startup
has a10-second watchdog and cleanup at most3additional seconds, all charged to
the shared budget. Later reference scoring must use the same budget guard.

Actors write a JSON response containing `move` (UCI), `piece_map` (all64 squares,
uppercase White pieces, lowercase Black, dot empty, question mark unknown),
`side_to_move` (white/black/unknown), and `confidence` (0..1).
`castling` records both colors' kingside/queenside rights as booleans or `unknown`;
`en_passant_square` is a square, null or `unknown`. These fields test fidelity to
the common rules metadata, not unaided visual inference. Then invoke only:

```sh
.venv/bin/python -m chesslab.position_trial submit private/trial initial initial-response.json
.venv/bin/python -m chesslab.position_trial submit private/trial final final-response.json
```

The command records the first submission at each stage exclusively. Malformed
and late responses remain evidence, with exact raw bytes in base64 and a digest;
they are not replaced by a clean retry. Late initial responses get no verdict.
Final submission never returns legality or evaluation scores. Both stages are
retained even when the final choice is unchanged. A missing final response is a
failure/missing observation, not a replacement sample. Format feedback is common
to all arms; source guards are an audit aid, not a filesystem or tool sandbox.

Post-response transcription scoring uses private occupancy only after decisions
are sealed. Board transcription errors, move legality, quality, scoring coverage
and wall latency are distinct outcomes. A copyable occupancy attachment cannot
prove improved intrinsic vision. Side-to-move accuracy under the shared banner
measures metadata fidelity. Reference scoring, paired family-cluster analysis,
sequence-memory tasks, lesson selection and final-test sealing need their own
verified evidence; preparing this module does not establish any of those results.

# Offline supplementary corpus

`chesslab.corpus` constructs private inputs for the prospective matched-position
study. It is evaluator-owned tooling and must never be imported or exposed in a
player context. Generated positions, engine traces, PGNs, images, and manifests
are private data, not source artifacts or chess-performance results.

The source implements the fixed twelve-prefix family map: three training,
three development, six final. Training/development checkpoints are plies 15/40;
final checkpoints are 15/24/31/40, giving 6/6/24 static items. Each family has
one legal nonterminal 40-ply generated game. Candidate seeds derive independently
from generation seed 2026111502, family ID, and attempt 1..10 by SHA-256. Failed
candidates remain in the construction log. Exhaustion stops construction; it does
not select another family or silently change the generation policy.

At each post-prefix ply, a seeded probability-0.8 branch chooses uniformly from
sorted unique UCI moves among at most three Stockfish MultiPV candidates at 1,000
nominal nodes. Otherwise it chooses uniformly from sorted legal moves. Every
query clears hash, supplies a fresh engine-game identity, and uses Threads=1,
Hash=16 MiB, Skill Level=20, strength limiting off, and an empty tablebase path.
Actual nodes, depth, time, candidate PVs and scores are private trace fields;
nominal nodes can overshoot. The binary hash, UCI identity/defaults/options,
Python/chess/PyMuPDF versions and source revision are recorded. Seeds and a pinned
single-thread engine aid reproduction, but elapsed times and platform-dependent
engine behavior are not promised byte-identical.

A query, including its hash reset, has a three-second watchdog. Engine startup
and configuration also have three-second bounds. Cumulative measured engine
work is limited to 30 minutes; timeout or engine failure stops the build rather
than replacing the candidate. Cleanup may take up to three additional seconds.
This builder records its consumed budget. Later assistance/reference scoring
must subtract that consumption from the study-wide 30-minute cap; starting a
new builder is not a fresh study budget.

Only checkpoint identities are deduplicated, both within a family and globally
across previously accepted families/splits. Identity uses piece placement, turn,
castling and *legally available* en-passant fields; counters are excluded from
identity but retained in full FENs and histories. Shared initial and intervening
frames are allowed and reused. This prevents exact checkpoint repeats; it does
not eliminate shared motifs, common prefix frames, or pretraining exposure.

## Rendering and files

The neutral renderer uses `chess.svg.board` with coordinates, default frozen
library theme, no arrows, last-move marker or check highlight; PyMuPDF rasterizes
390-unit SVG at scale 1.5 to 585-square PNG. SVG inputs are reproducible and their
SHA-256 appears in PNG filenames; SVG files are not stored. Both orientation
and canonical position enter the image cache. All arms reuse the same PNG bytes
for an item. No annotations, FEN strings, or oracle answers are embedded into
player JSON. Ordinary chess pieces and coordinates remain visible in the image.

Static orientation is White-bottom at ply 15 and Black-bottom at ply 40 for
training/development. Final orientation is White-bottom at 15/40 and Black-bottom
at 24/31, covering all side-to-move/orientation pairs per family. Sequence frames
0..40 always use White-bottom, avoiding orientation flips during memory tasks.
Final families supply two sequence definitions (0..24 and 0..40), each with four
probe checkpoints. The definitions contain images, order, and initial common
rules metadata; they contain no corrected history or probe answers.

One new private destination contains:

- `images/<SVG SHA-256>.png`: deduplicated rendered frames and static orientations.
- `player/p001.json` etc.: one static input per item, schema below.
- `player/sequences.json`: final sequence image references, probe plies, initial rules.
- `evaluator/items.json`: item-to-family/split mapping, full FEN, canonical FEN,
  occupancy and complete UCI history to the checkpoint.
- `evaluator/families.json`: accepted seeds/attempts, prefixes, full moves and all
  frames with private FENs/rules and shared image references.
- `evaluator/games/<family>.pgn`: complete source game for each accepted family.
- `construction.jsonl`: flushed start/candidate/query/move/rejection/acceptance
  records, or a final failure record; rejected moves remain available.
- `manifest.json`: success seal, provenance, policy, versions, counts and SHA-256
  of every other file. Its hash must be recorded separately as the commitment.

The revised design ceiling is 750 files and 12 directories, allowing all memory
frames; expected counts are lower through reuse. A manifest does not grant access
control. A controller must supply only the specific named player item/image and
explicit treatment attachments. It must never expose the evaluator directories,
construction log, manifest or unrestricted corpus-root browsing to actors.

A static player item has exactly:

```json
{
  "schema_version": 1,
  "item_id": "p001",
  "image": {"path": "images/<SVG SHA-256>.png", "sha256": "<PNG SHA-256>"},
  "orientation": "white",
  "rules": {
    "side_to_move": "black",
    "castling": {
      "white": {"kingside": true, "queenside": true},
      "black": {"kingside": true, "queenside": true}
    },
    "en_passant_square": null,
    "halfmove_clock": 1
  }
}
```

Castling/EP/turn/halfmove are common across every supplementary arm. This is an
image-plus-common-metadata control, distinct from the native unaided browser
baseline. Occupancy, FEN and moves occur only in evaluator records. Evaluator
`items` rows contain `item_id`, `player_path`, `family_id`, `split`, `ply`, `fen`,
`canonical_fen`, `history_uci`, and `occupancy` (square to case-sensitive FEN piece
symbol). All paths are relative to the corpus root.

## Execution boundary

Install `requirements-corpus.txt` in the isolated evaluator environment. After
independent source review, commit the implementation and freeze/amend the private
design before any final generation. The CLI requires a clean checkout and a new
destination below that checkout's `evidence/private/`:

```sh
.venv/bin/python -m chesslab.corpus \
  --output evidence/private/<new-corpus-id> \
  --engine /absolute/path/to/pinned/stockfish \
  --design evidence/private/supplementary-design.md \
  --design-sha256 <frozen-design-sha256>
```

The design SHA must match actual bytes. The source commit is read from Git.
Existing output is refused, including partial failed builds; preserve it rather
than restarting over it. Construction emits only the success manifest path,
counts and hash. No actors, references, treatment recommendations, schedule or
experimental outcomes are generated by this command. Schedule and bootstrap
seeds are committed metadata for downstream modules, not an implemented trial
orchestrator. No actual final corpus is generated by the unit tests: they use
synthetic names, a deterministic fake engine and temporary destinations. The
only real-renderer smoke uses the public standard starting board.

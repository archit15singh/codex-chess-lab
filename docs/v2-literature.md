# V2 methods background and bounded design advisory

Access date: **2026-11-16**. This is an M0 source review and prospective advisory
for [RESEARCH_PLAN_V2.md](../RESEARCH_PLAN_V2.md), not an M2 protocol freeze. It
contains no study outcomes. No players were collected, positions scored or prior
final items inspected for this review. Proposed numbers below are allocations,
not observed performance or demonstrated statistical power.

## What the empirical literature establishes

These four primary papers concern different tasks and training regimes. None
measures this study's specified Codex configuration operating a graphical board.
Reported ratings from other systems are not transferable calibration anchors.

### State tracking in a chess-trained language model

Shubham Toshniwal, Sam Wiseman, Karen Livescu and Kevin Gimpel. *Chess as a Testbed
for Language Model State Tracking*. AAAI 2022 extended version,
[arXiv:2102.13249v2](https://arxiv.org/abs/2102.13249v2), revised 2022-05-13.
[Author manuscript](https://arxiv.org/html/2102.13249v2).

The authors train transformer language models on move sequences and use chess
notation to probe piece tracking and legal-move prediction. Their experiments
show that access to full history matters under their training and attention
conditions. This is evidence about learned textual state tracking, not screenshot
recognition or an untrained general assistant's playing strength. It motivates
separating perception from state tracking and specifying exactly which history is
available. A current-board transcription probe alone cannot establish historical
memory: the answer may already be visible. V2 should query past events or states
that are not determined by the final observation.

### Search distilled into a specialized transformer

Anian Ruoss et al. *Amortized Planning with Large-Scale Transformers: A Case Study
on Chess*. [arXiv:2402.04494v2](https://arxiv.org/abs/2402.04494v2), revised
2024-10-21.

ChessBench supplies ten million games with Stockfish 16 annotations. The authors
train transformers of up to 270 million parameters and compare prediction targets,
including action values. Their resulting policy plays without explicit search at
inference. This is supervised chess specialization, including knowledge distilled
from an engine's search; it is not evidence that general-purpose Codex has the
same competence or that search is unnecessary in every configuration. For V2,
distinguish the unaided policy, increased reasoning effort and engine assistance.
Record the information and resource budget each receives rather than equating
their nominal settings. A prompt-based candidate is not model-weight training.

### Strategy and tactic explanations in supervised move selection

Shu Wang, Lei Ji, Renxi Wang, Wenxiao Zhao, Haokun Liu, Yifan Hou and Ying Nian Wu.
2025. *Explore the Reasoning Capability of LLMs in the Chess Testbed*. NAACL-HLT,
Volume 2: Short Papers, pp. 611–622.
[Publisher record](https://aclanthology.org/2025.naacl-short.52/),
[DOI](https://doi.org/10.18653/v1/2025.naacl-short.52).

The MATE dataset contains one million positions with candidate moves annotated
for strategy and tactics. The authors fine-tune LLaMA-3-8B and evaluate selection
of better candidate moves, reporting benefits from language explanations. Supplied
candidate moves, supervised specialization and explanatory annotations differ from
free move generation and graphical play. This supports testing a concrete lesson
mechanism, not assuming that a generic checklist improves Codex. Compare a
selected candidate with both the unchanged baseline and a matched sham; keep
candidate construction and selection outside the untouched test set.

### General-purpose models with explicit board and legality tools

Sai Kolasani, Maxim Saplin, Nicholas Crispino, Kyle Montgomery, Jared Quincy Davis,
Matei Zaharia, Chi Wang and Chenguang Wang. *LLM CHESS: Benchmarking Reasoning and
Instruction-Following in LLMs through Chess*.
[arXiv:2512.01992v1](https://arxiv.org/abs/2512.01992v1), submitted 2025-12-01.
[Full manuscript](https://arxiv.org/html/2512.01992v1).

This preprint evaluates over fifty models, primarily against a random opponent,
with additional engine comparisons and ablations. Its default agent can request a
textual board and legal moves; these are substantial assistance relative to V2's
screenshot-only baseline. The authors distinguish game results, move quality,
legality and instruction-following failures. V2 should retain that separation and
audit actual tools and error feedback. Its tool access, opponent pool and rating
procedure differ from this protocol, so its model ordering and rating estimates
are contextual background, not expected V2 outcomes. Text-board ablations also do
not isolate visual perception as a screenshot/state comparison would.

## Engine strength, reproducibility and rules

### Stockfish settings are configurations, not human ratings

The official [UCI command reference](https://github.com/official-stockfish/Stockfish/wiki/UCI-Protocol-and-Stockfish-Commands)
states that `UCI_LimitStrength` enables `UCI_Elo`, overriding `Skill Level`.
The documented Elo calibration uses **120 seconds + 1 second**, anchored to
**CCRL 40/4**. It does not calibrate a different node-limited browser experiment
to human Elo. The same reference describes `UCI_ShowWDL` as an approximate
engine-self-play model at fishtest LTC conditions, not the probability that this
Codex player wins. Its `go nodes` example overshoots the requested count; retain
actual nodes and stop times rather than treating the requested limit as exact.

The official [Stockfish FAQ](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html)
explains that weaker settings deliberately select suboptimal moves using a
randomized bias among candidates. The tagged
[Stockfish 19 search source](https://raw.githubusercontent.com/official-stockfish/Stockfish/sf_19/src/search.cpp)
initializes the skill-selection PRNG from the clock in `Skill::pick_best`.
Consequently, even a single-thread, fixed-node weakened opponent is not promised
to replay identical moves. Preserve the realized trajectory; do not rerun it to
obtain a preferred opponent line. Repeated realizations of the same opening
remain within an opening-family cluster.

A bounded local `uci`/`quit` handshake on the access date reported Stockfish 19,
binary SHA-256 `4f75fb47deaa8a29ddaaae206ab5edc6ebdfa9441e0e0fca3f15b95d9dae1c0f`.
It advertised `Skill Level` 0–20, `UCI_Elo` 1320–3190, default `Threads=1`,
`Hash=16` MiB, `Ponder=false`, `MultiPV=1`, empty `SyzygyPath` and
`EvalFile=nn-1a298aa575a0.nnue`. No random-seed option appeared. This verifies an
interface, not calibrated strength or subject performance. Record binary and
actual network bytes/hashes, all effective options, architecture and process/hash
lifecycle in M2. An advertised network filename alone is not a network hash.

For reference evaluation, use full strength, one thread, fixed hash, pondering
off, an explicit tablebase policy and a declared clean-state procedure. Freeze
whether every position gets a fresh engine or a reset and use it consistently.
Archive returned scores, mate/bound status, depth, actual nodes and termination.
Fixed nodes control one resource dimension; they do not establish equivalence
across builds, networks or configurations. Check reference stability on pilot
positions, then freeze the reference rule; do not selectively deepen final cases.

### Python-chess belongs to controller/evaluator roles

The official [engine documentation](https://python-chess.readthedocs.io/en/latest/engine.html)
describes explicit `Limit` values for nodes, time and depth. Analysis without a
limit is unbounded. `play`/`analysis` send the board's move stack; changing the
`game` identifier sends the new-game signal. Use these deliberately, plus an
external timeout and preserved actual stop evidence. A nominal engine limit is
not a host-process watchdog.

The official [core documentation](https://python-chess.readthedocs.io/en/latest/core.html)
warns that `Board.push()` does not validate legality and `is_valid()` checks basic
validity, not historical reachability. Replay known legal histories and validate
each move before pushing it. Preserve the stack for repetition; a final FEN is not
a complete game history. Freeze draw claims: `outcome(claim_draw=False)` handles
automatic endings, while fifty-move and threefold claims require explicit policy.
Do not equate a budget stop with a chess draw. Also distinguish a raw FEN
en-passant square from an available legal capture: `fen()` defaults to legal-only
en-passant notation, whereas `fen(en_passant='fen')` preserves the raw target.
State each target literally in the actor brief and scorer specification.

These libraries may operate the legal environment or audit it afterward. They
must not expose board truth, move lists or evaluator hints to an unaided player.

## One allocation that fits the envelope

This is an arithmetic feasibility proposal, subject to pilot latency, completion,
difficulty and precision checks. It is not a powered design. Define disjoint
training, development and final source families before sampling descendants.
Use four training families, four development families and twelve final families
as a starting taxonomy. Six final opening families supply the games; twelve final
source-family groups supply diagnostics. Cross-suite ancestry links remain in the
manifest. A shared ancestor means one cluster, not two independent families;
family labels alone do not create statistical independence.

### Games: 64 assigned, including four pilot games

| Cohort | Calculation | Assigned games |
| --- | --- | ---: |
| Pilot, separate families | Four feasibility games covering the proposed opponent range | 4 |
| Final unaided baseline | 6 opening families × 2 colors × 3 opponent settings | 36 |
| Final selected candidate | Same 6 families × 2 colors × 1 prespecified opponent | 12 |
| Final matched sham | Same 6 families × 2 colors × that opponent | 12 |
| Total | | **64** |

The candidate/sham comparison reuses the twelve baseline games at the selected
opponent setting; it does not launch twelve more. Freeze that setting using pilot
feasibility alone. Example pilot configurations are `UCI_Elo=1320,1800,2400` with
`UCI_LimitStrength=true` and a common finite node limit. Those numbers are labels
to investigate, not promised useful separation or calibrated ratings. Four pilot
games cannot precisely calibrate three strength levels. If they do not support a
useful range and feasible completion, revise the allocation prospectively at M2
or report the needed amendment; do not assert separation from option names.

Collect the final competitive benchmark only after candidate selection is frozen,
or keep every final outcome inaccessible to developers until selection. Reverse
colors within opening pairs and randomize condition/order within blocks. The
primary candidate comparison has six family clusters, not twelve independent
games or hundreds of independent moves. Expect coarse, potentially wide
uncertainty and no assurance of promotion.

### Diagnostics: 408 assigned, leaving 104 unassigned

| Cohort/comparison | Matched structure | Assignments |
| --- | --- | ---: |
| Pilot | Mixed feasibility probes, separate families | 48 |
| Training diagnosis | 4 families × 9 tasks, baseline only | 36 |
| Development selection | 4 families × 3 items × 5 arms: baseline, sham, candidates 1–3 | 60 |
| Final perception | 12 families × 4 items × screenshot/state | 96 |
| Final genuine history | 12 families × 2 sequences × internal/external history | 48 |
| Final injected-error correction | 12 families × 2 proposals × feedback/no feedback | 48 |
| Final reasoning/search | 12 families × 2 items × baseline/increased reasoning/bounded search | 72 |
| Total | | **408** |

The three candidates are three total policies, including revisions. A common sham
fits this table only if all three candidates have the same delivery, length and
interaction structure; otherwise budget candidate-specific shams before launch.
Use the same frozen development tasks across arms, balanced order and fresh
contexts. Select one policy by a predeclared rule, not by choosing its best
endpoint. The remaining 104 assignments are unspent capacity, not replacements
or permission to expand after seeing final results. More pilot/development work
would consume this reserve before final freezing and remain in the global ledger.

Balance orientation, theme and clutter across perception blocks; this sample does
not power every interaction. Score exact transcription and move consequences
separately. For history, expose identical current frames across conditions and
query earlier captures, order or checkpoint contents with balanced truth targets.
Verify that the answer cannot be uniquely reconstructed from the last frame.
Use final-board-matched alternative histories where feasible. Each table entry is
one scored player assignment; if a sequence has four separately prompted stages,
it consumes four assignments per condition and requires reallocation. Do not hide
extra stages or correction attempts inside an assignment count.

Keep diagnostic intervention effects distinct: validated state is extra
information; external history is retrieval support; legality feedback is explicit
assistance; bounded search is an assisted configuration. These comparisons do not
add up to a decomposition of chess intelligence. A genuine-history retrieval gain
alone does not establish a later game-playing benefit.

### Attempt, engine and stopping arithmetic

An illustrative per-game cap of **50 player move-decision attempts**, counting
illegal proposals and permitted resubmissions, gives `64 × 50 = 3200`. Reserving
one move-decision attempt for each of the 408 diagnostics gives **3608**, below
4000. Even charging the entire 512-diagnostic ceiling would give **3712**, leaving
288 attempts. A transcription-only response need not be a move decision, but
charging it conservatively avoids hidden capacity. Any additional decision in a
multi-stage or repair workflow consumes the ledger too. No run ID resets it.

Fifty decisions may censor long games. Pilot this explicitly: a capped unresolved
game is an operational noncompletion with unknown chess result, never an invented
draw or loss. Keep assigned-game operational scores, completed-game W/D/L and
missing-game bounds separate. If this cap leaves the core competitive question
unanswerable, M2 must change the allocation or seek a resource amendment rather
than silently converting the experiment into short-game diagnostics.

Illustrative node ceilings are 20,000 per opponent move, 20,000 per assisted search
and 200,000 per reference call, with at most two reference calls per decision.
Conservatively charging all 512 diagnostic slots an assisted search and allowing
one extra opponent opening move per game gives `(3200 + 64) × 20000 +
512 × 20000 + 4000 × 2 × 200000 = 1,675,520,000` requested nodes. Additional
opening/setup searches need their own reservation or must be avoided.
Requested-node overshoot, process initialization and pilot calibration
also consume aggregate engine wall time. These are proposed ceilings, not a
throughput measurement or assurance that the reference is stable. An aggregate
7200-second engine wall cap and 10-GB evidence cap can provide additional stops;
the M2 pilot must verify feasibility, including finite per-call watchdogs and
storage headroom. A cap exhausted during scoring yields explicit unavailable
measurements, not selective reruns or a renewed budget.

Freeze the sample and schedule once at M2. Preserve all failed assignments,
timeouts and missing references; no replacement game, retry cohort or further
candidate follows an unfavorable final result. Keep the 90-second decision and
60-minute game defaults only if pilot evidence supports their actual clock
enforcement. The envelope is a maximum, not a reason to spend unused capacity.

## Decisions M2 must settle

Reserve and hash final families before candidate development. Exclude all prior
final items and answers from training, selection and player contexts without
opening them for this advisory. Detect duplicate/transposed source positions and
shared histories across splits; distinguish unavoidable common chess positions
from reused task instances. Candidate developers get only training/development
feedback. Evaluation answers and reference output remain with the evaluator.

Predeclare one improvement endpoint and a selection rule before development
scores exist. A possible minimum effect of interest is **0.10 game-score points
per assigned game**, with **25% median wall-time overhead** as an illustrative
cost tolerance. These are judgment choices to approve at M2, not values inferred
from literature. Define how operational failures enter that endpoint and report
actual chess-result bounds separately. A content-specific claim additionally
needs the candidate/sham contrast, with a prespecified multiplicity or hierarchical
rule. A positive point estimate with unresolved uncertainty is not promotion.

Simulate intervals and promotion operating characteristics using family clusters,
paired colors, shared baseline observations, stochastic opponents and plausible
missingness. Average within family, then weight families equally; resample shared
family indices across arms and endpoints. Report leave-one-family-out sensitivity.
Do not claim a six-cluster bootstrap has demonstrated nominal coverage. If using
an exact sign-flip reference, state exchangeability assumptions and include ties
exactly; it is not automatically a causal randomization test. Treat the twelve
diagnostic families and repeated probes accordingly. Either accept the resulting
wide uncertainty or change the prospective allocation within the remaining cap;
do not relax the promotion standard after outcomes are known.

Freeze endpoint direction, unknown/abstention handling, eligible denominators,
conditional answered cohorts, confidence scoring, history target definitions,
feedback text, engine assistance and draw/censoring rules. Report truth baselines
on the same evaluated cohort. Rejecting all candidates or obtaining inconclusive
effects is valid; omitting a required comparison is not completed execution.

The cited literature does not establish suitable difficulty, visual readability,
latency, reference stability, rating calibration, isolation or power for the
present host. Those remain empirical engineering/pilot gates before M2.

# Experimental protocol v0.4

Status: prospective design; feasibility is separate from confirmatory evidence.
Freeze a version and hashes before the pilot. Amendments retain dated reasons.
Version0.2 addressed independent methodological review. Version0.3 added an
immutable mechanical runtime and controller-supplied move-start deadlines after
observed collection/timing failures. Earlier runs retain their frozen records and
are identified separately in the amendment ledger; changes are not retroactive.
Version0.4 adds a logged promotion continuation, a sealed harness-stop record
that preserves unresolved actions, and an explicit controller-preparation budget
anchor. Promotion and stop handling are mechanical amendments, not chess lessons.

## Questions and estimands

The target is Codex-through-Brave performance on Duolingo, not the strength of a
chess engine. Primary endpoints are game completion without intervention and
score against a defined opponent under a defined interface. Report attempted
moves, accepted moves, retries, illegal intents and timeouts separately. Secondary
endpoints are post-game move loss, tactical accuracy and decision latency.
Unknown model identity or hidden effort settings preclude model-specific claims.

## Conditions

| Condition | Observation and tools | Purpose |
| --- | --- | --- |
| Unaided | Screenshot + coordinate input; internal context only | Frozen baseline |
| State | Baseline + validated representation | Perception intervention |
| History | Baseline + external move-history record | Memory intervention |
| Legality | Baseline + move validator | Legality intervention |
| Search | Baseline + declared bounded search | Tool contribution |
| Engine reference | Explicit Stockfish assistance | Assisted upper reference |
| Reflection | Fixed trained lessons, frozen at test entry | Agent adaptation |

State, history and legality need matched/factorial comparisons, not only cumulative
addition. Use common positions with randomized condition order in independent
contexts. Keep model, reasoning, opponent, color, time control and task version
fixed within each matched comparison. Define the exact state fields, their oracle
source and error feedback before an ablation. Treat side to move, castling rights
and en-passant information as additional channels if not visually observable.
A legality treatment must not silently return engine rankings. Test history on
identical screenshot sequences with storage as the changed factor; isolated static
positions alone cannot establish state-tracking memory benefit. Record treatment availability, actual tool
calls, hardware, software and execution budgets. Actual session capabilities,
not desired model names, determine feasible treatments.

## Separation and leakage

Feasibility runs never enter the pilot. Begin a fresh player context per baseline
game, without earlier game results, tactical answers, PGN, retrieved chess lessons,
external FEN, legal-move libraries or search. Controller/evaluator access is not
player access. Log host tools and inspect their content. Abandon the label
'unaided' if a forbidden information channel reaches the player; preserve the
run as a protocol deviation rather than silently discarding it.

Allocate training and held-out units before reflection. Split by game/opening
family and position identity, not random moves from the same game. Hash split
manifests before evaluation. Public benchmarks have potential pretraining exposure;
generated unseen legal positions reduce reuse but do not prove no contamination.
The current developer/researcher context is unsuitable as a frozen baseline.
Use training data to generate lessons, development data to select candidates, and
a locked final test for the frozen selected candidate. Never revise from final-test
answers and then reuse those items as held out. Repeated development comparisons
are exploratory and do not constitute independent confirmatory replications.

## Pilot and resource policy

First perform one visual feasibility game. Then a ten-game unaided feasibility
pilot, balanced colors where the product permits and randomized run order. Oscar
is adaptive; record its visible setting and history effects rather than treating
it as a calibrated fixed opponent. If color or opponent control is unavailable,
report it and use common-position tests as additional evidence, not a replacement
for specified full games. This sequential adaptive-account pilot is descriptive
and conditional on that account history; it does not establish IID opponents.
Only an independently controlled design can support an independent-game
uncertainty model; matched positions cannot retroactively calibrate Oscar. No new paid API or recurring jobs without approval.
Initial limits: one live game at a time, no new move started after a controller-
supplied deadline20minutes after recorded controller preparation immediately
before player task launch (record both timestamps, preparation overhead, actual platform
semantics and actual elapsed time), at most200attempted agent moves, two
recovery observations before marking an interaction failure. An official platform timeout loss is a completed game loss when the UI verifies
that outcome. A harness wall timeout is an aborted run unless the platform
independently confirms a game outcome. Unresolved execution remains incomplete
until observed; never invent a win/loss or silently replace that run. Report all
started games and each failure category, plus completed-game score separately. Token/cost metadata unavailable from the
host remain unknown. Do not invent budget control that the host does not expose.

After the pilot, estimate variance and clustered failure rates. Choose a fixed
extension sample and stopping rule based on precision targets before collecting
it. No repeated significance checks with optional stopping. Ten games are a
feasibility pilot, not enough to support a grandmaster claim.

## Independent post-game analysis

Reconstruct PGN after completion, retaining perception uncertainty. Verify every
move and final board with a chess library, and compare every transition with raw
screenshots. Only then run Stockfish at fixed recorded node budget, Threads=1,
fixed Hash and exact engine binary hash/version. Analyze best and selected moves
from the same position and side-to-move perspective. Report mate scores separately
instead of assigning arbitrary centipawns. Predeclare a blunder threshold (initial
candidate 200 cp; sensitivity 100/300) before confirmatory scoring. Record engine
limits, not only its nominal depth. Never infer human Elo from average loss.

## Statistics

Use raw denominators and score fractions with draws worth one half. Wilson95%
completion intervals require independent game-level Bernoulli observations.
If that assumption is unverified (including adaptive Oscar), label any interval
as an IID sensitivity calculation whose nominal coverage is not established;
use descriptive counts as the primary pilot result. Paired
comparisons and clustered bootstrap by game/opponent/opening handle dependence;
move-level rows are not independent game replicates. Bootstrap seeds and resample
counts must be recorded. Estimate relative ratings only against a calibrated
opponent pool with explicit model assumptions and uncertainty; never equate
Duolingo rating, engine skill settings, FIDE Elo and benchmark-local ratings.
The move-start deadline does not preempt an already executing native action or
final observation. A later platform timeout after a harness stop is a separate
follow-up outcome, not uninterrupted completed play. Keep software/protocol
versions as analysis strata when mechanics changed.
No data means 'not estimated', not zero ability. An inconclusive comparison is a
valid outcome; a missing experiment is not an inconclusive measured result.

## Failure taxonomy and improvement

Classify perception (piece/square/orientation/turn), state drift, illegal choice,
strategic/tactical error, coordinate execution, animation timing, UI recovery,
protocol contamination, missing evidence and unknown causes separately. Preserve
both initial failure and recovery, with evidence references.

Post-game loop: audit completed training run -> group evidenced failures -> propose
one specific lesson -> freeze a version -> compare against control on development
data -> select and freeze a candidate -> evaluate once on a locked final split ->
estimate paired uncertainty -> retain, reject or mark inconclusive. Archive that
final split from further adaptive tuning and use a new untouched final split for
any later revised candidate.
Keep lesson scope, provenance, training IDs, test manifest hash and version. The
baseline never receives these lessons. This is prompt/memory adaptation; no claim
of changed weights. Infrastructure changes need tests; chess advice needs held-out
performance evidence. Neither substitutes for the other.

## Permission and release

Bot study proceeds under user-attested permission, recorded privately with date
and scope. Human matches need disclosed participation, participant consent and
platform authorization. Never use random unsuspecting humans as controls. Public
source PRs are authorized; research results, raw screenshots and participant data
remain local pending publication review. Final report: self-contained HTML in
artifacts/, PDF in output/pdf/, reproducible figures from auditable actual data,
explicit unknowns, and a requirement-by-requirement completion audit.

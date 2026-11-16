# Codex Chess Lab V2: controlled strength and measurable improvement

**Version:** 2.0, prospective specification, 2026-11-16.
**Activation:** Run the separate [goal prompt](GOAL_PROMPT_V2.md) explicitly. Writing,
reviewing or merging these files starts no experiments.
**V1:** [RESEARCH_PLAN.md](RESEARCH_PLAN.md) remains the historical V1 contract.
Preserve its datasets, frozen protocols, candidates and completed reports.

## 1. Research question and scope

How well does a specified Codex configuration play chess through a graphical
browser, where does performance fail, and can a bounded improvement procedure
produce a reproducible gain on previously unseen tasks at an acceptable cost?

This study separates competitive results, interaction reliability and component
diagnostics. It does not require a positive improvement result or a particular
rating. Evidence may support a narrow conclusion with wide uncertainty. Missing
required experiments still mean incomplete execution.

The primary environment is a small, local chess board operated through Brave,
with a controlled engine opponent. This deliberately changes the environment
from V1's Duolingo study to control opponent settings and opening assignments.
Permitted Duolingo play is an optional ecological extension, reported separately.
Human competition is a separate extension requiring consent and suitable rating
calibration; neither extension is necessary for the core definition of done.

Initial design choices here are prospective engineering defaults. Verify them
before collection. Preserve amendments with dates, reasons, affected cohorts and
whether any relevant outcomes were already visible. Final results never become
development data for this study. A material design change requires a new cohort,
identifier and prospective analysis; it cannot repair a frozen result in place.

## 2. Questions, comparisons and allowed claims

| Question | Required comparison | Primary evidence |
| --- | --- | --- |
| Competitive strength | Frozen unaided player against multiple fixed opponent settings | Assigned-game score, W/D/L, completion, intervals by opponent |
| Perception | Screenshot observation versus validated state on matched positions | Exact board and square accuracy; decision quality separately |
| Historical memory | Matched sequences with and without external history | Accuracy on past information unavailable from the final board |
| Correction | Fixed illegal proposals with and without legality feedback | Correction success and cost, separate from spontaneous illegality |
| Reasoning and search | Baseline versus increased reasoning budget versus bounded search assistance | Matched quality, reliability, latency and observed resource use |
| Improvement | Selected candidate versus frozen baseline and matched sham | Untouched-test effect, uncertainty, resource cost and promotion decision |

Component comparisons estimate the specified intervention's effect. A collection
of such comparisons does not identify an additive decomposition of intelligence.
Predeclare confirmatory endpoints; treat other comparisons as exploratory and
control multiplicity or explicitly avoid confirmatory claims about them.

Report benchmark-local performance. Stockfish's advertised strength settings,
centipawn loss, puzzle accuracy and wins against one bot cannot establish a FIDE,
human Elo or grandmaster rating. An optional relative rating model needs an
identified anchor, checked fit and uncertainty; label its pool and conditions.
Correlated settings of one engine are not independent opponent populations.

## 3. Architecture and information boundaries

Reuse the existing collector, immutable runtime snapshots and separate evaluator
where they fit. Read [architecture](docs/architecture.md),
[browser collector](docs/browser-collector.md), [evaluator](docs/evaluator.md) and
[protocol](docs/protocol.md) for existing mechanics. Their V1 scientific settings
do not silently become the V2 protocol. Prefer files, the existing local database
and small commands over a new service or orchestration framework.

Four roles have explicit input/output contracts:

1. **Player:** receives the condition's permitted observation and emits an intended
   move or coordinate action. Start a fresh context for each independent game or
   diagnostic assignment. Preserve within-game context according to its condition.
2. **Controller:** supplies observations, applies intended actions, verifies the
   result and records timing. It may know board truth to operate the environment;
   its messages to the unaided player contain only allowed UI observations.
3. **Opponent:** selects the opposing side's moves using frozen engine settings.
   Its analysis and best moves are not exposed as player hints.
4. **Evaluator/auditor:** verifies trajectories and computes reference scores after
   the player's assignment has ended. Its outputs remain outside player channels.

The unaided player gets screenshots, ordinary visible game feedback and mechanical
coordinate actions. No reconstructed FEN, DOM, hidden application state, legal
move lists, chess libraries, engine recommendations, opening lookup or persistent
chess lessons enter that context. Environment rules enforcement is distinct from
player assistance; any additional legality feedback is an explicit treatment.
Validated-state, history, reasoning and search configurations each declare their
extra input and budget. A direct-state diagnostic is not a screenshot-only game.

Audit actual host traces and exposed tools, not the player's self-description.
Describe procedural isolation honestly; controller access to truth is not an OS
sandbox or proof of operator blindness. Use blinded condition IDs where possible.
If the host cannot enforce a boundary, downgrade or invalidate the affected claim
and build an auditable alternative before collecting the final cohort.

## 4. Experimental design and resource contract

### Freeze before final collection

Pilot data may determine feasibility, difficulty and sample allocation. Then seal
one V2 protocol containing the full assignment manifest, split hashes, prompts,
model/effort settings, runtime hash, random seeds, opponent settings, time rules,
endpoints, exclusions, estimators, intervals, multiplicity policy and stopping rule.
Record available model metadata and unknowns; do not invent an exact backend
snapshot. Stratify or amend prospectively if the observable configuration changes.

Use disjoint training, development and final families, including opening families
and source-position families. Keep all V1 final items outside candidate training,
selection and new player contexts. Researchers may inspect the prior study's
methods and engineering failures without feeding its final answers to candidates.
Hash the reserved final assignments before candidate development; keep answers
with the evaluator and reveal them only after candidate selection is frozen.

For games, pair openings with colors reversed, randomize condition order within
blocks and balance opponent settings. Record stochastic engine behavior and
seed control actually available. Treat opening pairs/families as dependent groups;
moves within a game and repeated seeds are not independent sample size. Use enough
independent families for the intended uncertainty claim. Document overlap when a
baseline assignment serves more than one comparison and account for it in analysis.

For diagnostics, eligibility and difficulty strata depend on position truth or
development observations, never final model success. Freeze correction, history
and perception scoring before answers are collected. Sampling may intentionally
target difficult cases; inference then applies to that challenge distribution.

### Bounded execution

These are initial maximums for the core study, across all pilots, conditions,
retries and unsuccessful candidates: **64 assigned games, 512 diagnostic player
assignments, 4,000 player move-decision attempts and three candidate policies** in
one improvement cycle. A paired item presented to three conditions consumes three
assignments. Preflight consumes at most eight games and 48 diagnostic assignments
from those totals. Software tests using deterministic fixtures consume no subject
assignments and never count as capability evidence.

Only one game owns the browser at a time. Start with a 90-second player decision
deadline and a 60-minute game wall limit; pilot evidence may support a documented
change before final freezing. Define clocks from observed execution timestamps,
including queue and timeout handling. Enforce each limit at its actual boundary;
a deadline for starting is not a hard deadline for stopping a running model.

Before launching subjects, estimate model use and engine cost with available
counters, set a finite engine node/time cap and disk allowance, and reserve enough
of the envelope for every required held-out comparison. Use the smallest useful
sample rather than spending the entire cap by default. Existing host resources
are the default; new paid services or consequential spend require permission.
Record actual usage, wall time and overruns. Tokens, latency and engine nodes are
different measures; none alone establishes billing cost or model FLOPs.

After the pilot, choose and freeze a feasible fixed sample with a stated precision
target and minimum effect of interest. Simulate uncertainty using the true
clustering and missingness assumptions. If the cap implies a wide interval,
report that limitation prospectively. Prefer fixed stopping with no outcome-based
peeking. A sequential design requires valid prospective boundaries. Never reset
the cap with new run IDs or extend collection until a desired gain appears.
If required comparisons cannot fit, report an incomplete program and the exact
resource amendment needed; do not quietly drop a question or claim completion.

## 5. Milestones and acceptance evidence

Maintain private V2 progress, decisions, discoveries and outcomes under
`evidence/private/v2/`, linked from the task checkpoint. Each milestone records
acceptance, observed evidence paths/hashes, independent verification and the next
action. Use PASS, FAIL, BLOCKED or INCONCLUSIVE with reasons. An inconclusive
effect can be scientifically valid; a missing implementation cannot pass.

### M0 — Inspect, research and establish the route

Inspect the live worktree, dependencies, existing tests, prior private checkpoint,
actual model/tool access and browser state. Read relevant primary literature and
current official documentation, including engine strength calibration. Reconcile
existing permission records with the intended route. Reuse permission already
established for unchanged scope; never bypass platform restrictions. Continue
local engineering if a third-party route is unavailable.

**Accept:** a source-linked feasibility record, resource estimate, V1 preservation
inventory and reviewed design covering every required comparison. Verify at least
one feasible browser observation/action path. An unavailable Duolingo extension
does not block the local controlled study.

### M1 — Minimal controlled browser chess

Implement a local board with legal game progression, frozen opponent settings and
a screenshot/coordinate adapter. Test castling, promotion, en passant, turn
ownership, terminal positions, draws, resignations and clock semantics using known
fixtures. Preserve intend -> act -> observe -> verify evidence. Observe before
retrying an uncertain click; prevent duplicate actions and concurrent owners.
Opaque raw error payloads stay private; safe metadata references preserve diagnosis
without exposing hidden answers in player channels.

**Accept:** meaningful integration checks and one complete logged autonomous pilot
game, independently replayed against the visible trajectory. Record the installed
engine binary/network hashes, UCI options, Threads/Hash and node or time settings.
The opponent and post-game evaluator may share a binary but have separate roles
and declared configurations. Engineering tests alone do not demonstrate strength.

### M2 — Pilot, power/precision analysis and protocol freeze

Run the bounded pilot with fresh contexts. Estimate latency, failure rates,
reference-score stability, diagnostic ceiling/floor effects and group variation.
Allocate the remaining envelope across the competitive benchmark, component
comparisons and final candidate/baseline/sham test. Reuse matched tasks across
comparisons only when declared and analyzed as dependent.

**Accept:** independently reviewed prospective protocol and hashed assignments,
numeric final samples, precision expectations, finite budgets, baseline prompt,
reference-evaluation policy and promotion threshold. Include every required arm;
resolve ambiguous scoring before final data exist. Keep pilot outcomes outside
final estimates. Seal the candidate-development/final split before M4 begins.

### M3 — Controlled strength and component measurements

Run the frozen unaided competitive benchmark. Cover at least three fixed opponent
settings if the pilot verifies distinct useful difficulty; justify any change
before freezing. A single easy opponent is insufficient. Log all assignments,
starts, completed results, failures, move attempts and resource use.

Run the matched component suites from section 2:

- **Perception:** vary orientation, visual theme and interpretable clutter. Score
  exact boards and square-level errors against truth; separately assess decision
  consequences. Track ambiguous/unknown responses rather than forcing guesses.
- **Memory:** query earlier states, move order or captures that the final board
  does not uniquely reveal. Balance targets and baserates, include matched
  alternatives ending in the same visible board where feasible, and score all
  required fields independently. Distinguish legal en-passant opportunities from
  a raw FEN field. Measure retrieval separately from later playing benefit.
- **Correction:** present externally fixed illegal proposals with a randomized
  feedback treatment. Score corrected legal moves and cost. Label injected errors
  separately from spontaneously illegal proposals in ordinary play.
- **Reasoning/search:** compare declared reasoning budgets with a bounded search
  treatment on matched tasks. Freeze search nodes/time and information returned.
  Search-assistance gains belong to that configuration; the unaided baseline
  remains unchanged. Record unequal realized resource use rather than claiming
  equal compute from a nominal setting.

**Accept:** actual held-out observations for every required comparison, complete
assignment accounting, independently replayed games and audited player channels.
An effect near zero or a wide interval passes execution only if the prospective
sample and integrity checks pass. Preserve contaminated trials and classify them;
do not substitute conveniently successful replacements.

### M4 — Bounded self-improvement

Implement one reusable loop: classify training failures -> propose one bounded
change -> test on development -> record decision -> select and freeze -> evaluate
once on untouched final families. This may overlap M3 operationally, but candidate
developers remain blind to M3 final outcomes and answers until selection freezes.

Develop at most three candidate policies, including revisions, within the shared
assignment cap. Change one declared mechanism per candidate, such as a decision
checklist or retrieved lesson; record its inputs and costs. Freeze the unchanged
baseline and a matched sham before testing. The sham matches the intervention's
extra context/interaction budget while omitting the chess lesson being tested.
Match achieved cost where practical and report residual differences. Explicit
memory or engine help changes the condition label and cannot become unaided gain.

Select one candidate using only the preregistered development rule, freeze its
prompt/artifact hashes, and run candidate/baseline/sham on matched untouched tasks.
Predeclare a primary improvement endpoint, minimum meaningful gain, uncertainty
criterion and allowed latency/resource tradeoff. Prefer game score where the
sample supports it; a diagnostic-only gain warrants only a diagnostic claim.
Apply the frozen promotion rule even if the candidate loses. No final-test tuning,
repeated attempts, selective candidate reporting or model-weight training.

**Accept:** a tested reusable loop, complete candidate/selection ledger, frozen
baseline/candidate/sham, actual final comparison and an evidence-backed promote
or reject decision. Rejecting every candidate is a valid result. A further cycle
needs new untouched data, a new prospective protocol and an explicit resource
amendment; it is outside the core V2 completion requirement.

### M5 — Statistics, audits and failure analysis

Compute W/D/L and score (win=1, draw=0.5, loss=0) for completed games. Also report
all-assigned delivery/reliability and a prospectively defined operational endpoint
where failed assignments receive zero credit. Label that endpoint separately from
chess score. Report missing-game bounds and reasons; do not turn harness failures
into invented board losses or silently condition all claims on successful starts.

Use the frozen matched/grouped estimators and suitable intervals. For few groups,
show finite-sample limits and appropriate exact or sensitivity checks. Count
independent groups, not just moves. Audit inclusive tails, rounding, denominators,
ties and multiple comparisons. Do not interpret failure to reject as equivalence.

Analyze move quality with a stronger frozen reference configuration, after the
player ends. Establish its budget with the pilot, including stability checks.
Handle mate scores, bounds, missing evaluations and perspective explicitly;
report coverage and finite-search inversions. Never selectively increase search
only for awkward results. The primary competitive evidence remains actual games.

Classify perception, memory, illegal choice, weak strategy, interaction, timeout,
infrastructure and contamination failures using evidence, allowing uncertain or
multiple causes. Examine successful runs too. Distinguish observed associations
from causal findings supported by randomized interventions.

**Accept:** independently reproduced tables and key estimates, a claim-to-evidence
map, full missingness/failure ledger, uncertainty and resource accounting. Have an
independent reviewer challenge leakage, selection bias, rating claims, adverse
results and the promotion decision. Resolve material issues before writing claims.

### M6 — Paper, visual report and reproducible package

Write a full research paper: abstract, motivation, related work, methods,
preregistration/amendments, results, ablations, improvement procedure, failure
analysis, limitations, ethics/permissions, reproducibility and conclusion.
Separate prior literature, V1 context and newly observed V2 results. Cite primary
sources; keep sensitive records local and use anonymized IDs.

Produce a self-contained dark HTML report using the HTML-artifacts skill and a
research-paper PDF using the PDF skill. Use standard plotting tools for shareable
scientific figures. Include uncertainty and denominators in figures, a strength
curve by opponent, component effects, improvement comparisons, reliability/failure
distribution and quality-versus-latency/resource plots when data support them.
Supply exact-value tables and accessible captions; mark absent evidence plainly.

Keep V2 outputs under `artifacts/v2/` and `output/pdf/` with distinct V2 names.
Preserve private raw records, assignment/config hashes, tool/model metadata,
source commit, dependency/engine versions, candidate histories, analysis code and
instructions in a local reproducibility archive. Generate a manifest with hashes.
Separate public source from private evidence; sanitize staged files explicitly.

**Accept:** regenerate central results from preserved inputs in a clean local
directory, verify archive readback/hashes, inspect HTML interactions in Brave,
extract/check PDF text and render and inspect every PDF page for clipping,
readability and figure fidelity. Independent review reconciles paper, figures,
tables and ledger. Source-only PRs are reviewed, green and merged to main.
Creating a paper locally does not authorize external publication.

## 6. Agent operation, repair and continuity

Before each collection batch, verify runtime manifests, assignment ownership,
player tool contracts and budget counters. Record a unique intent before launching
a subject. Prove the previous subject ended before evaluator access or replacement.
Recover interrupted work by reading the checkpoint and inspecting actual live
state; a queued intent or alias is not proof that a subject started or stopped.

Keep append-only attempts and raw evidence. Deterministic retries have prospective
rules and consume the original envelope. A timed-out final subject is a recorded
failure, not an invitation to sample a fresh answer. Fix engineering defects with
focused regression checks; freeze repaired runtimes for subsequent assignments,
preserving affected earlier trials and amendments. Do not rerun an intact frozen
benchmark to make a source change look successful.

Use a short entry point, clear module contracts and commands that expose actual
configuration. Update operational documentation when behavior changes. At each
verified milestone, checkpoint workspace/branch, runtime, active owners, evidence
paths, checks, limitations and next action using the shared workspace checkpoint
mechanism; keep task-specific V2 state separate from V1's completion record.
After context loss, verify the checkpoint against files and processes before
resuming. Use supported subagents for independent review and bounded parallel
engineering, with one owner per mutable artifact and no parallel browser play.

Progress through reviewed milestones without recurring permission gates. Escalate
only for required authentication, unresolved platform permission, consequential
spending, participant consent, destructive actions or external publication.
Continue independent authorized work while a dependency is blocked. Apply the
host's actual Goal lifecycle rules when reporting a blocked or resource-limited
state; keep a resumable record and never call unfinished work complete.

## 7. Definition of done

Mark the V2 Goal complete only when all of these have verified evidence:

1. V1's specification and original evidence/reports remain preserved; V2 provenance,
   permissions, resource bounds and prospective amendments are recorded.
2. The controlled Brave environment works end to end, with meaningful mechanics
   checks and independently verified actual autonomous game trajectories.
3. The frozen non-pilot strength benchmark has run to its prespecified stop, with
   multiple controlled opponent settings, paired colors/openings and uncertainty.
4. Every required component comparison in section 2 has actual held-out data,
   valid scoring and independently audited information boundaries.
5. The bounded improvement loop has run through selection, freeze and one final
   candidate/baseline/sham evaluation with the frozen promotion rule applied.
6. Every assignment and candidate, including no-starts, failures, contamination and
   missing scores, is accounted for; observed resource use and limitations appear.
7. Independent statistical review reproduces central estimates and challenges
   leakage, selection, dependence, uncertainty and unsupported strength claims.
8. A complete research-paper PDF and visual self-contained HTML report exist,
   agree with the evidence, and pass text, interaction and visual inspection.
9. The private reproduction archive passes extraction, manifest readback and
   regeneration of central results; all major claims have evidence pointers.
10. Authorized source changes are reviewed, checked and merged to main; the final
    checkpoint and handoff identify deliverables, limitations and any next study.

Negative or precision-limited findings can satisfy these criteria. An unavailable
required arm, integrity failure, unfinished collection or exhausted budget cannot.
Report the exact unmet criterion and what would unlock it. Optional human or
Duolingo extensions may remain unrun with explicit status and no borrowed claims.

## 8. Goal-design research and source notes

Consulted official sources on 2026-11-16. These inform the specification, not an
empirical result about Codex chess ability:

- [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex):
  define an outcome with observable evidence, constraints, allowed scope, an
  iteration policy and a defensible blocked exit. The prompt delegates detailed
  scientific criteria to this file and makes bounded negative findings valid.
- [Developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli):
  `/goal` objectives are limited to 4,000 characters. Keep the copyable prompt
  within that limit; durable details belong in a referenced file. Verify current
  host availability rather than assuming identical interfaces everywhere.
- [Using PLANS.md for multi-hour problem solving](https://developers.openai.com/cookbook/articles/codex_exec_plans):
  use resumable plans, explicit milestones and maintained decision/evidence logs.
  This archived recipe supplies planning ideas, not current API/model guarantees;
  V2 uses the repository's existing plan and private checkpoint conventions.
- [Stockfish UCI protocol and commands](https://github.com/official-stockfish/Stockfish/wiki/UCI-Protocol-and-Stockfish-Commands):
  strength limiting depends on engine options and calibration conditions. Record
  the installed version and settings; a configured engine Elo is not a measured
  Codex human rating. Verify current engine documentation again at M0.

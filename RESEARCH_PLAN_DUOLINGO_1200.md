# Duolingo 1200: chess performance, component diagnostics and improvement

Prospective follow-up specification, version 0.2, 2026-11-18. The user explicitly
started the [goal](GOAL_PROMPT_DUOLINGO_1200.md). This document does not assert that
any game, rating gain or experiment has occurred. Preserve V1 and the stopped V2
study; neither supplies final outcomes for this study or resumes automatically.

## Outcome and scope

Study Codex operating Duolingo Chess Web through Brave, attempting to finish the
bounded program with a displayed rating of at least 1200. Report starting rating,
every observed change, first crossing and final rating separately. Duolingo Elo
is specific to its player pool; it is not a FIDE, Chess.com or Lichess rating.
An account's inherited rating and mixed-policy trajectory are not an estimate of
unaided Codex strength. A rigorously measured failure to reach 1200 is a valid
research result, but the target remains explicitly unachieved.

Oscar bot play is the initial route under the existing user-attested research
permission. Verify its recorded scope against the actual collection method.
Anyone play requires the platform and participant conditions in
[the human-play protocol](docs/protocol.md#permission-and-release). Establish the
actual mode, opponent type and time control; do not infer a human or a bot from a
name or avatar. Keep unresolved Anyone work pending while independent authorized
bot research proceeds. Friend matches require consenting participants and
authorized contact. No recruitment, spending or external research publication is
authorized by this plan.

Use supported visible UI interaction. Retain permission provenance privately.
Reuse established authorization for unchanged scope. Stop an affected route on
an anti-bot restriction, authentication challenge or material permission mismatch;
continue independent work. Read current policies rather than importing rules
from another chess service.

## Six dimensions and evidence

| Dimension | Contrast | Outcomes and limits |
| --- | --- | --- |
| Perception | Screenshot versus validated visible piece placement on the same position | Exact placement and square accuracy; move quality separately. Hidden castling or en-passant fields are not screenshot perception targets. |
| Memory | Final screenshot alone versus explicitly supplied earlier screenshots/history | Accuracy on fixed past-state questions whose answers are not uniquely recoverable from the final board; distinguish retrieval from playing benefit. |
| Reasoning | Frozen baseline effort versus one supported higher effort on matched tasks | Legal response, bounded reference quality, latency and observed usage. Nominal effort does not establish equal or known compute. |
| Search | Baseline versus a fixed, bounded engine hint on matched offline tasks | Assisted decision quality and cost; engine access stays outside live baseline and human matches. |
| Self-improvement | Frozen baseline, matched sham and selected candidate on untouched tasks | Assigned-item quality, reliability, cost and a predeclared promote/reject decision. A lesson policy is a distinct configuration, not weight training. |
| Interaction reliability | Intent/action/observation records in every game; fixed injected illegal proposals with and without visible legality feedback offline | Accepted actions, uncertain/rejected actions, timeouts and correction success. Injected corrections are separate from spontaneous illegality. |

These estimate the specified interventions. They do not identify an additive
decomposition of intelligence. Keep live ecological results separate from offline
diagnostics, and label exploratory analyses.

## Roles and reusable mechanics

Reuse the [native collector](docs/browser-collector.md), immutable runtime
snapshots, ledger, post-game evaluator and existing analysis tools. Prefer small
files and commands to another orchestration framework. A source/test pass proves
engineering behavior, not chess ability.

The controller owns Brave, captures observations and mechanically applies the
player's unchanged intended actions. The unaided player is a fresh context per
game, receives screenshots and ordinary visible feedback, and retains its own
within-game context. It receives no reconstructed board state, legal move list,
engine output, opening lookup, earlier experimental game or learned policy.
Candidate, sham, state, history and search arms declare their additional inputs.
Evaluator and policy-development contexts stay separate from live players.
Every diagnostic arm and replicate starts in its own fresh independent context,
receiving only that arm's frozen inputs. Randomize arm order and assignment to
fresh context slots within each matched item. Seal every response before
returning any paired-arm output, reference label or feedback to another context.
History supplied within one assigned arm is distinct from context shared across
arms. Record actual context identities and audit these boundaries.

Record the actual host instructions and available tools as well as tools used;
procedural isolation is not an OS sandbox. Audit original host traces, including
initial host envelopes, extra inputs, image bytes, calls, returns and lifecycle
timestamps. Unknown inputs remain findings. Preserve raw logs; a parser exception
cannot silently delete evidence or supply scientific validity.

Before the pilot, record an available player model alias, baseline effort,
supported higher effort, model metadata and unknowns. Freeze the same model alias
for the final comparisons. Scientific model/effort dispatch overrides follow that
frozen protocol; engineering agents inherit their host defaults. A backend
snapshot is unknown unless independently provided. Record host or tool-format
changes prospectively and disclose their affected roles and phases.

## Bounded design

Initial ceilings for this independently requested follow-up are **48 initiated
games, 102 diagnostic player assignments, 2,880 live move attempts and three new
candidate policies in one cycle**. Every attempted, incomplete and invalid run
counts; no reset, replacement or refund. Preserve earlier study ledgers and record
both study-specific and cumulative project use. These ceilings do not alter or
restart V2's contract. No collection begins until the private cumulative ledger
states how this follow-up relates to the earlier resource envelope; a conflicting
hard limit requires an explicit prospective amendment, not a new run ID.

Allocation, subject to pilot feasibility and a recorded freeze before final data:

- Six training games, including at most two integration pilots.
- Six development games; freeze the candidate count before development and
  assign these six slots in candidate-index round-robin order. One, two or three
  candidates receive six, three or two games each. Select at most one candidate.
- Thirty-six final games: twelve baseline, twelve sham and twelve selected-policy
  games, assigned in twelve randomized blocks of three.
- Six diagnostic pilots, excluded from final estimates.
- Ninety-six final diagnostic assignments: six matched pairs for each of
  perception, memory, reasoning, search and legality feedback (60 assignments),
  plus twelve matched baseline/sham/candidate triples (36 assignments).

This allocation prioritizes the primary improvement comparison over descriptive
component precision. It was revised during plan review, before any pilot or final
response; the six-item improvement design had very coarse exact-test resolution.

Before final collection, freeze model/prompts, seeds and ordered assignments,
permitted modes, source-game sampling, scoring, references, deadlines, missingness,
estimators and promotion arithmetic. Anyone can be included only after its route
is authorized and its conditions are frozen. Unavailable human play is a reported
route limitation; it cannot be silently replaced and called Anyone evidence.

The live platform may not permit fixed openings or opponents. Randomization then
assigns policies to game slots, not identical chess tasks. Preserve opponent
ratings, mode and time controls when visible; report adaptive opponents, repeated
opponents, account carryover and temporal effects. The final game comparisons are
exploratory; a rating trajectory alone is not a causal improvement estimate.

Reserve twelve distinct diagnostic source games by final-game slot before
collection. Each component's six matched pairs use six distinct source games;
the twelve improvement triples use all twelve distinct source games. A source
game is the inferential unit, with its arms kept together; positions or moves
from the same game never become additional independent units. Use a
deterministic, outcome-independent rule for positions and historical questions,
frozen before their responses. Developers cannot inspect final games or reserved
tasks. Validate board/history labels using visible records and independent legal
replay; when truth cannot be established, preserve the assigned item as missing.
No favorable resampling or access to V1/V2 final answers is permitted. Generated
controlled tasks may supplement feasibility only, unless prospectively declared
as a separate final distribution before affected responses.

Use one browser owner and one scientific player at a time. Pilot the platform's
actual timing, then freeze finite decision and game limits that respect its
clocks. Record admission, observation, query, submission, action and actual-stop
timestamps separately. Interrupt and poll the same running handle after a limit;
retain overruns and never start a replacement because observation timed out.
After an uncertain click, observe before recovery and preserve the pending intent.

Offline search uses at most 20,000 nodes and a two-second operation limit per
assigned hint. Post-response references initially use at most 100,000 nodes and
five seconds per position; score mate and missing results separately. Freeze
binary/network/options and reference stability rules. The follow-up engine
allowance is at most 30 minutes measured process time, within any unreleased
project-wide cap. Retained follow-up artifacts are limited to 2 GB, with at least
5 GB free. Check resources before collection and conserve enough for all required
arms. Existing host resources are the default; paid additions need approval.

## Improvement, inference and missing data

Classify only training failures. Propose one to three policies of at most 120
words, including revisions, changing one declared mechanism each. Freeze all
policies and their count before the six development slots. Test each on its
assigned round-robin slots, with no outcome-based reallocation. Select by highest
assigned-game score proportion, then fewer invalid
decisions, then lower total decision latency, then candidate index. Preserve
every unsuccessful policy. Freeze baseline, selected policy and a sham with
matched extra context length before final games. Do not tune or reselect after
final exposure. If development cannot support a valid selection, record that
failure; do not invent a candidate or omit the required final comparison.

The primary improvement endpoint is assigned diagnostic success: a legal,
timely response with bounded reference regret at most 100 centipawns. Freeze the
side-to-move convention, mate handling and finite-reference stability rule before
collection. Missing, late, malformed, contaminated or unscorable items receive
zero primary success, with their reasons and sensitivity bounds also reported.

Promotion requires selected-policy gains of at least two successes out of twelve
against both baseline and sham, both one-sided exact paired tests passing Holm
at family level 0.05, completion no worse than baseline, and median assigned-item
latency at most 1.5 times baseline. All twelve costs per arm must be known and
nonnegative, and the baseline median must be positive; unknown cost fails
promotion. Use source-game paired binary differences and inclusive exact tails;
retain zero differences as ties in the accounting. Specify the randomization
reference and discrete ties in the frozen executable analysis. A failed criterion
rejects promotion.

Report live W/D/L, assigned-game score, completion and rating trajectory, keeping
pilot/development separate. For component contrasts, report all assigned items,
paired effects, source-game clustering, missingness and bounded uncertainty.
Twelve or six source games give weak precision; bootstrap percentiles are
descriptive sensitivity summaries, not automatically validated confidence
intervals. Source games shared across dimensions are dependent. Multiplicity for
the two confirmatory improvement tests is separate from descriptive component
analysis. Do not condition the main result on successful tool use or completion.

Finish the fixed allocation even after an early 1200 crossing. Stop at a declared
hard budget or permission boundary, not at a favorable effect. Reaching 1200 does
not waive the research deliverables; exhausting the budget does not prove strength.

## Milestones and definition of done

Each milestone records acceptance, original evidence, independent verification,
limitations and the next action under `evidence/private/duolingo1200/`.

1. **Route:** verify visible Oscar/Anyone controls, rating meaning, policies,
   permission scope, history/export capability, cumulative resources and a native
   observation/action path. Resolve human scope before matchmaking; continue
   independent authorized work.
2. **Pilot and freeze:** complete two logged bot pilots, independently replay
   visible trajectories, verify six diagnostic pilots and record timing/resource
   feasibility. Independently review and seal the final protocol and assignments.
3. **Train, develop, freeze:** finish the six training and six development games;
   retain policy inputs, selection ledger, frozen candidate and sham. Seal final
   diagnostic sampling without exposing final answers to development.
4. **Final collection:** complete the fixed permitted game and diagnostic arms,
   preserving every assignment and failure. Independently audit full player
   channels, trajectories, labels, clocks and resources before final scoring.
5. **Analysis and reproduction:** apply the frozen estimators and promotion rule;
   independently check statistics and claims, regenerate actual tables/figures
   from preserved inputs in a clean extraction, and verify archive hashes.
6. **Paper:** produce a full local PDF with abstract, related work, methods,
   prospective amendments, results across all six dimensions, improvement decision,
   rating trajectory, failures, uncertainty, limitations, permissions and
   reproducibility. Include data-derived figures and tables. Render every PDF page
   for text and visual QA; inspect a self-contained dark HTML companion in Brave.
   Keep raw account/participant data private and publication separately authorized.
7. **Source and handoff:** reviewed passing source PRs merged to main, private
   reproducible archive and evidence-linked final requirement audit; checkpoint
   all remaining limitations. Tests or plans alone cannot satisfy this program.

The research goal can complete with a verified negative rating/improvement
result after its required permitted program and package are finished. A missing
required experiment, unresolved integrity failure or unfinished paper remains
incomplete. Keep the active goal's status honest and preserve a resumable
checkpoint when a route is blocked.

## Primary-source starting points

Recheck these against the live account before relying on mutable product facts:

- [Duolingo Chess course](https://blog.duolingo.com/chess-course/): web offering
  and opponent options.
- [Duolingo Elo](https://blog.duolingo.com/what-is-an-elo-rating-in-chess/):
  platform-specific ratings and game updates.
- [Game Review](https://blog.duolingo.com/chess-game-review/): announced mobile
  history/review; verify web capability separately.
- [Terms](https://www.duolingo.com/terms) and
  [Guidelines](https://www.duolingo.com/guidelines): current route restrictions.

Use the skill router for research, review, HTML artifacts and PDF production.
Apply the PDF artifact-start marker immediately before first PDF authoring, then
render and inspect every page. Protocol authorship itself creates no results.

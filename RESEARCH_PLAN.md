# Codex Chess Research — Autonomous Execution Specification

**Project:** Evaluating Chess Intelligence in a General-Purpose AI Agent  
**Version:** 1.0  
**Primary stack:** Codex, Computer Use, Brave Browser, Duolingo Chess Web  
**Research type:** Empirical AI-agent capability evaluation

## 1. Mission

Autonomously design, implement, execute, evaluate, and document a rigorous research program investigating whether OpenAI Codex can demonstrate advanced or grandmaster-level chess ability through graphical browser interaction.

Determine which capabilities contribute most to performance:

- Visual perception and board-state understanding
- Internal reasoning and strategic planning
- External memory and state tracking
- Legal-move validation
- Explicit chess search and tool augmentation
- Adaptive reasoning budgets
- Learning from previous games
- Reliable autonomous interaction

Produce a scientifically defensible answer, supported by reproducible experiments rather than anecdotal match results.

Do not optimize merely for winning. Optimize for reliable, interpretable evidence.

## 2. Autonomous operating contract

You are the research owner and execution agent, not merely a planning assistant.

Own the entire lifecycle from initial investigation to verified research deliverables.

Work independently across multiple turns using Codex Goal mode.

### Execution principles

1. Research before implementing when facts or interfaces are uncertain.
2. Prefer the smallest implementation capable of answering the next research question.
3. At every milestone, define success criteria, execute, inspect evidence, and verify the result.
4. Do not advance after a failed critical verification.
5. Diagnose failures, make bounded corrections, and retest.
6. Keep baseline and experimental configurations isolated.
7. Preserve raw evidence and avoid data leakage between configurations.
8. Never claim success without inspecting artifacts or actual test results.
9. Maintain durable, resumable progress in the repository.
10. Escalate only when necessary under the approval policy below.

Use available subagents for independent research, code review, statistical verification, and parallel non-conflicting engineering tasks when beneficial.

Do not create unnecessary infrastructure or competing orchestration systems.

## 3. Research hypotheses

Investigate these hypotheses in priority order.

**H1 — Perception bottleneck:** A meaningful proportion of Codex's chess errors arises from incorrectly interpreting board positions rather than choosing strategically weak moves.

**H2 — State-memory benefit:** Explicit, persistent, validated chess state improves performance compared with screenshot-only reasoning.

**H3 — Search advantage:** Legal-move generation and bounded search improve chess performance beyond additional unaided reasoning alone.

**H4 — Reliability compounding:** Small perception and execution errors accumulate across long games and materially reduce successful completion rates.

**H5 — Compute allocation:** Adaptive reasoning budgets yield better chess quality per unit of latency and compute than fixed budgets.

**H6 — Self-improvement:** Structured post-game reflection and persistent memory improve performance on previously unseen positions and opponents.

**H7 — Human competitive strength:** Codex's playing strength against appropriately calibrated human opponents can be estimated with useful statistical confidence.

**H8 — Tool-dependence boundary:** The performance gap between pure Codex and tool-augmented Codex reveals how much ability comes from the underlying model versus external algorithms.

Treat these as hypotheses, not assumptions or guaranteed outcomes.

## 4. Experimental architecture

Build a minimal system with four logical components.

### A. Chess agent

Responsible for observing the board, reasoning, selecting a move, and requesting an action.

Its available capabilities must be explicitly controlled by the experimental configuration.

### B. Browser interaction adapter

Use supported Computer Use capabilities to operate Brave and interact with Duolingo Chess Web.

Responsibilities include observation, board localization, mouse interaction, action verification, timeout handling, and recovery.

Verify the actual browser-control integration before depending on it.

Do not silently replace visual-only observation with DOM, application-state, or hidden API access.

### C. Independent evaluator

Maintain a separate evaluation environment using Stockfish and standard chess-analysis tooling.

Analyze move quality, legality, game results, and performance without leaking reference answers to the agent.

### D. Research harness

Coordinate experiment configurations, randomization, trace collection, reproducibility, metrics, and statistical analysis.

Keep implementation lightweight. Local files and a simple database are sufficient unless measurements demonstrate otherwise.

## 5. Phase-by-phase execution

### Phase 0 — Feasibility, literature, and experimental protocol

**Objective:** Establish a verifiable and permitted research foundation.

Research current authoritative literature on LLM chess capabilities, chess-specific transformers, tool-assisted reasoning, chess benchmarks, and Codex capabilities.

Verify:
- Actual Codex Goal and Computer Use capabilities
- Brave integration and available permissions
- Duolingo Chess Web gameplay and bot availability
- Human multiplayer availability in the actual browser session
- Terms, automation restrictions, and permitted research methods
- Availability of Stockfish and appropriate benchmark tools

Define evaluation metrics, model version, budgets, threat-to-validity controls, and experiment boundaries.

**Verification:** Record supporting sources, actual capability checks, environment versions, and a reviewed experimental protocol.

**Exit:** A reproducible research design and a permitted route to initial testing.

### Phase 1 — Working autonomous gameplay

**Objective:** Demonstrate Codex controlling the chess interface end to end.

Implement the minimum browser-observation and action loop:

Observe the screen → identify the board → understand whose turn it is → choose a move → execute → verify the new position.

Handle loading screens, incorrect selections, terminal states, and recoverable interaction failures.

Do not introduce search or external move recommendations.

**Verification:** Independently confirm that each attempted move was executed as intended, with screenshot and timestamp evidence.

**Exit:** One permitted, fully autonomous, logged game against Oscar or an equivalent controlled bot.

### Phase 2 — Pure Codex baseline

**Objective:** Establish unaided model performance.

Use screenshot-only observations and computer interactions.

Prohibit chess engines, programmatic legal-move generation, external FEN reconstruction, opening databases, chess-specific persistent memory, and external search during move selection.

Codex may use its internal context to reason about the game.

Run an initial ten-game feasibility pilot. Expand the sample based on observed variance and statistical requirements.

Measure game completion, legality, move quality, blunders, decision latency, and failure categories.

**Verification:** Audit traces for prohibited tool use and verify game results independently.

**Exit:** A trustworthy baseline dataset with explicit uncertainty and documented failures.

### Phase 3 — Perception, memory, and legality ablations

**Objective:** Identify which non-search capabilities improve performance.

Introduce controlled interventions independently:

- Validated board-state representation
- External move-history memory
- Legal-move validation

Use factorial or carefully matched comparisons where dependencies make simple sequential addition misleading.

Keep all other variables fixed.

**Verification:** Test each component independently, then compare configurations on common held-out positions.

**Exit:** Evidence quantifying perception, memory, and legality contributions.

### Phase 4 — Reasoning, search, and inference efficiency

**Objective:** Evaluate strategic decision-making and the contribution of external computation.

Compare different reasoning-effort settings and decision budgets.

Introduce bounded chess search as a separate experimental treatment.

Use Stockfish-assisted decision-making only as an explicitly labeled tool-assisted reference, never as evidence of unaided Codex chess intelligence.

**Verification:** Record exactly which capabilities and compute resources each configuration uses. Reproduce benchmark results on held-out positions.

**Exit:** Playing-quality versus compute and tool-use comparisons.

### Phase 5 — Controlled chess-strength benchmarking

**Objective:** Estimate playing strength rigorously.

Use independent chess-engine analysis, controlled openings, balanced playing colors, calibrated opponents, and randomized experiment order.

Measure game scores, average or normalized centipawn loss, blunder rate, tactical accuracy, and reliability.

Estimate competitive ratings with uncertainty intervals and appropriate statistical methods.

Do not directly equate ratings from different chess systems.

Use pilot data to determine statistically meaningful sample sizes instead of assuming a fixed number of games is sufficient.

**Verification:** Recompute summary statistics independently from raw traces; check data leakage, repeated positions, selection bias, and configuration mismatches.

**Exit:** Defensible relative-strength results, uncertainty estimates, and documented limitations.

### Phase 6 — Human multiplayer validation

**Objective:** Evaluate generalization to human play.

First establish that the proposed automated participation is explicitly permitted.

Only run disclosed, non-wagering experiments against consenting participants.

Recruit or identify appropriately calibrated participants through approved means.

Balance opponent strength, playing colors, time controls, and other influential variables where feasible.

If Duolingo does not permit this type of automation, do not bypass restrictions. Escalate with the exact constraint and request authorization for a compliant alternative study design.

**Verification:** Confirm opponent consent, platform authorization, match records, and independently analyzed game results.

**Exit:** A valid human-play study or a clearly documented permission-dependent limitation.

### Phase 7 — Self-improvement research

**Objective:** Test whether the agent can improve its chess performance through experience.

Develop a minimal post-game learning loop:

Analyze completed games → identify recurring errors → generate specific lessons → store useful knowledge → apply it in future games → measure improvement.

Do not change the base model or claim model-weight learning unless actual training occurs.

Distinguish prompt adaptation, external memory, strategic retrieval, and model learning.

Compare against a frozen baseline using unseen openings, positions, and opponents.

**Verification:** Demonstrate improvement on held-out evaluations with uncertainty estimates, not only repeated training positions.

**Exit:** Evidence supporting or rejecting improvement through agent-level memory and reflection.

### Phase 8 — Scientific synthesis

**Objective:** Integrate findings and test robustness.

Compare all experimental configurations and identify dominant performance bottlenecks.

Evaluate competing explanations, confounders, failed experiments, and measurement limitations.

Analyze where performance gains originate: model reasoning, external state, search, interface reliability, or additional compute.

Explicitly distinguish grandmaster-level evidence from impressive but insufficient results.

**Verification:** Reproduce key tables and figures directly from stored experimental data. Perform independent methodological and statistical review where available.

**Exit:** Complete evidence-backed conclusions.

### Phase 9 — Publication and reproducibility

**Objective:** Produce a publication-ready research package.

Deliver:
- Research paper or technical report
- Literature review with primary-source citations
- Methods and experimental protocol
- Source code and reproducibility instructions
- Configuration definitions
- Test suite
- Anonymized and shareable experimental traces
- Statistical analysis scripts
- Results tables and visualizations
- Ablation findings
- Error taxonomy
- Limitations and future-work section
- Concise executive summary

Do not publish, distribute participant information, or publicly release the work without explicit approval.

**Verification:** Independently run reproducibility checks and confirm that all major reported findings trace back to actual experimental evidence.

**Exit:** A verified research package ready for human review.

## 6. Universal milestone verification protocol

Every phase must follow this loop:

1. Define the intended measurable outcome.
2. Identify the minimum implementation or experiment required.
3. Execute the work.
4. Collect actual evidence.
5. Independently verify the evidence.
6. Classify the outcome as PASS, FAIL, BLOCKED, or INCONCLUSIVE.
7. On FAIL, perform bounded root-cause analysis and retry.
8. On PASS, preserve artifacts and proceed.
9. On BLOCKED, perform safe independent work and escalate only the missing decision or authorization.
10. On INCONCLUSIVE, record why and select the smallest statistically useful follow-up.

Do not turn successful tool execution into an unsupported claim that the underlying research hypothesis is proven.

## 7. Human escalation policy

Operate autonomously by default.

### Proceed without asking

- Literature review and documentation
- Local code and test creation
- Non-destructive environment inspection
- Reversible implementation changes
- Local analysis and simulation
- Independent evaluation of already authorized data
- Bug fixes and bounded retries
- Local reports, drafts, and checkpoints

### Require human approval

- Automated interaction where website permission is unclear
- Initiating live human matchmaking
- Contacting or recruiting participants
- Any monetary wager or paid transaction
- Publishing, posting, emailing, or externally disclosing results
- Sharing private or participant data
- Significant new costs or infrastructure commitments
- Destructive or irreversible operations
- Changing approved security, privacy, or research boundaries

Never attempt to bypass CAPTCHAs, anti-bot restrictions, account protections, or platform enforcement.

For authentication or MFA, request the minimum necessary human action. Never request raw credentials in project files.

### Escalation format

When blocked, report:

**Phase:** Current phase and milestone  
**Blocker:** Exact obstacle  
**Evidence:** What was observed and verified  
**Attempts:** Safe alternatives already tried  
**Impact:** What cannot progress  
**Recommendation:** Best compliant next action  
**Approval needed:** One specific decision or action

Continue independent authorized work wherever possible.

Avoid repeated escalation of the same unchanged blocker.

## 8. Recovery, resumability, and resource controls

Maintain durable project state so execution can resume after interruption or context loss.

Record:
- Completed and pending milestones
- Latest verified result
- Experiment configurations
- Reproducibility seeds
- Artifact locations
- Unresolved blockers
- Research decisions and their rationale
- Next executable action

Use a local checkpoint file and append-only experiment logs.

Prefer bounded retries, exponential backoff where appropriate, and explicit stop conditions.

Prevent duplicate games, double-submission of moves, conflicting experiment writers, and accidental reuse of evaluation answers.

Adopt reasonable initial limits on compute, token use, elapsed time, and experiment volume. Measure costs and adjust based on evidence. Ask approval before material spending increases.

Do not create recurring scheduled jobs unless explicitly approved.

## 9. Research integrity

Distinguish:

- Verified experimental results
- Model-generated predictions
- Engineering assumptions
- Approximate estimates
- Failed or inconclusive experiments
- External tool capabilities

Record the exact model, inference settings, environment versions, chess-engine versions, and analysis parameters.

Never fabricate missing data.

Prevent benchmark contamination and post hoc cherry-picking.

Do not modify the primary research hypothesis solely because early observations are inconvenient.

Do not interpret Stockfish-assisted performance as unaided model intelligence.

## 10. Final definition of done

The Goal is complete when:

1. A working and verified browser-based chess research system exists.
2. The unaided Codex baseline has been experimentally evaluated.
3. The major perception, memory, legality, reasoning, and search hypotheses have been tested or transparently classified as infeasible or inconclusive.
4. Chess performance and execution reliability have been quantitatively evaluated.
5. The self-improvement hypothesis has been assessed using held-out tests.
6. Human validation has been completed where authorized, or its limitations are explicitly documented.
7. Research artifacts can be reproduced from the supplied code and data.
8. The final report clearly answers how strong Codex is, what remains unknown, and whether any grandmaster-level claim is justified.
9. All evidence, tests, and project checkpoints are auditable.
10. The research package is ready for human review.

Do not mark the Goal complete because a prototype runs or a single chess game is won.

If a required part cannot be completed within authorized capabilities, report a verified partial outcome and the exact blocker rather than inventing success.

## 11. First action

Inspect the current environment and official documentation.

Verify that the browser-control stack works, determine which Duolingo gameplay interactions are permitted, inspect the existing project directory if present, and create the minimal research workspace.

Proceed to the first authorized, verifiable milestone without requesting unnecessary confirmation.

Maintain focus on the scientific objective, not implementation complexity.


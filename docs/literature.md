# Primary-source literature review

Observed 2026-11-15. This is a targeted review, not a systematic review or a reproduction of published results. All performance numbers below are the original authors' claims about their own systems. None measures the Codex agent in this repository.

## State tracking and representation

Toshniwal, Wiseman, Livescu and Gimpel (AAAI 2022), [Chess as a Testbed for Language Model State Tracking](https://cdn.aaai.org/ojs/21390/21390-13-25403-1-2-20220628.pdf), study move-sequence language models. Their experiments separate piece tracking from legal-move prediction, and report benefits from explicit state during training with smaller datasets and degradation with restricted game history. Read: abstract and introduction. These are trained text models, not screenshot-based agents.

**Design inference:** score board interpretation independently of move quality. A move error cannot establish a perception failure without a separately verified board. Compare history and validated-state treatments independently rather than assuming they are interchangeable.

## Chess-specific transformers and the meaning of searchless

Ruoss et al. (2024), [Amortized Planning with Large-Scale Transformers: A Case Study on Chess](https://arxiv.org/html/2402.04494v2), train chess-specific transformers with Stockfish annotations. They report a policy reaching 2895 Lichess blitz against humans, while discussing differences between human and bot rating pools. Their discussion also describes a Stockfish fallback in overwhelmingly winning positions. Read: abstract, introduction, discussion and limitations.

**Design inference:** inspect the complete deployment policy before calling a system unaided or searchless. Training on engine evaluations is different from inference-time engine access; neither is evidence about general-purpose Codex. Do not translate a Duolingo display rating, engine skill setting, Lichess rating or FIDE rating into another scale without calibration.

## Full-game agentic evaluation and inference budgets

Kolasani et al. (2025), [LLM Chess: Benchmarking Reasoning and Instruction-Following in LLMs through Chess](https://arxiv.org/html/2512.01992v1), evaluate models using board-state, legal-move and move-submission tools. They report instruction-following failures, model-dependent effects of representation and legality assistance, benefits from increased reasoning effort, and limited gains from some multiple-proposer settings. Read: design, metrics, test-time scaling, ablations, and appendix C.1. The appendix records FEN feedback after illegal moves even in alternative representation conditions, an important treatment-fidelity detail. Its findings concern its historical models and tool-rich protocol.

**Design inference:** use completed games as well as static positions; record failed attempts, timeouts and tool feedback; do not pool extra reasoning with search. A screenshot-only baseline is stricter than this paper's main protocol. Inspect actual prompt and tool transcripts when auditing a condition.

## Strategic explanations and fine-tuning

Wang et al. (NAACL 2025), [Explore the Reasoning Capability of LLMs in the Chess Testbed](https://aclanthology.org/2025.naacl-short.52/), introduce MATE and fine-tune LLaMA-3-8B to compare candidate moves with strategic and tactical explanations. Read: publisher abstract and paper introduction/method excerpts. Candidate-choice accuracy with supplied annotations differs from generating and executing moves through a browser.

**Design inference:** natural-language lessons are a plausible intervention, not an established benefit for Codex. Evaluate them against a frozen agent on unseen positions, with identical inference budgets.

## Recent preprints: verification and specialized models

Tang (May 2026), [Generalization or Memorization? Brittleness Testing for Chess-Trained Language Models](https://arxiv.org/abs/2605.17565), argues that strong chess-puzzle performance can remain brittle and reports gains from a verifier-in-the-loop. Read: abstract only. These claims have not been independently reproduced here.

Bhaskar, Cheng and Chen (October 2026), [Language Models that Play Chess and Explain Their Moves](https://arxiv.org/abs/2610.03695), introduce Queen, combining a chess expert encoder, language model and iterative distillation. Read: abstract only. The claimed grandmaster-level performance concerns that specialized architecture, not Codex.

**Design inference:** distinguish prompt adaptation, retrieval, specialized encoder assistance and actual model training. Hold out entire games/opening families and retain provenance for every lesson; high performance on repeated puzzles cannot demonstrate general improvement.

## Synthesis and remaining gap

The sources motivate separate measurements of state tracking, legality, strategic quality, interaction reliability and computation. They do not determine current Codex chess strength. The missing experiment is controlled, permitted browser play with independently verified state and outcomes. Literature examples must never be inserted into the project's experimental results table. Published puzzles remain possible pretraining exposures; generated held-out positions reduce direct reuse but do not prove an absence of contamination.

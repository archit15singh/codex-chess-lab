# Verification gates

Statuses refer to phase exit criteria, not effort spent. Evidence is local until
reviewed for disclosure. The private checkpoint is the source of current run state.

| Phase | Acceptance evidence | Current status |
| --- | --- | --- |
| 0 Foundation | Literature, live browser/permissions audit, versions, reviewed protocol, independent evaluator smoke test | IN PROGRESS; protocol and sources drafted, evaluator engine pending |
| 1 Gameplay | Complete autonomous bot game, every action screenshot, independent game/trace audit | IN PROGRESS; live feasibility executed, audit pending |
| 2 Baseline | Ten-game pilot, fresh isolated contexts, tool audit, uncertainty | NOT STARTED |
| 3 Ablations | Matched state/history/legality tests with verified splits | NOT STARTED |
| 4 Compute/search | Recorded budgets, isolated treatments and held-out results | NOT STARTED |
| 5 Strength | Calibrated opponents, balanced controls, reproducible statistics | NOT STARTED |
| 6 Humans | Platform permission plus disclosed consenting participants, or explicit limitation | PERMISSION DEPENDENT |
| 7 Improvement | Frozen lessons vs control on held-out positions with uncertainty | NOT STARTED |
| 8 Synthesis | Claim-to-evidence map, regenerated tables/figures, independent review | NOT STARTED |
| 9 Package | Verified HTML/PDF, methods, code/data, reproducibility and completion audit | NOT STARTED |

Engineering checks: `python3 -m unittest discover -s tests -v`. These are neither
experimental games nor proof of any research hypothesis. Update the relevant
status only after inspecting its acceptance evidence. Preserve failures and
inconclusive results; never promote a preliminary report to the final package.

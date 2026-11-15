# Verification gates

This file lists stable phase exit criteria. Live statuses and their evidence
references belong in the private checkpoint, avoiding a stale public copy of
research progress. Evidence remains local until reviewed for disclosure.

| Phase | Acceptance evidence |
| --- | --- |
| 0 Foundation  |  Literature, live browser/permissions audit, versions, reviewed protocol, independent evaluator smoke test |
| 1 Gameplay  |  Complete autonomous bot game, every action screenshot, independent game/trace audit |
| 2 Baseline  |  Ten-game pilot, fresh isolated contexts, tool audit, uncertainty |
| 3 Ablations  |  Matched state/history/legality tests with verified splits |
| 4 Compute/search  |  Recorded budgets, isolated treatments and held-out results |
| 5 Strength  |  Calibrated opponents, balanced controls, reproducible statistics |
| 6 Humans  |  Platform permission plus disclosed consenting participants, or explicit limitation |
| 7 Improvement  |  Frozen lessons vs control on held-out positions with uncertainty |
| 8 Synthesis  |  Claim-to-evidence map, regenerated tables/figures, independent review |
| 9 Package  |  Verified HTML/PDF, methods, code/data, reproducibility and completion audit |

Engineering checks: `python3 -m unittest discover -s tests -v`. These are neither
experimental games nor proof of any research hypothesis. Update the relevant
status only after inspecting its acceptance evidence. Preserve failures and
inconclusive results; never promote a preliminary report to the final package.

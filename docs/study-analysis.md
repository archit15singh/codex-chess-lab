# Static endpoint contrasts

`python -m chesslab.study_analysis INPUT --schedule SCHEDULE --output NEW_OUTPUT` analyzes one endpoint
matrix. Input has `rows`; every row contains a unique `unit`, a source `family`
and `values` with exactly A through I. The CLI requires the frozen static schedule,
checks exact item/family membership and unique complete nine-treatment assignments,
and commits both input hashes. An omitted assigned item is an error. Complete
host/scorer audits before exporting the matrix: this statistical program cannot
attest that a model followed its treatment. The pure Python function can omit its
schedule for mathematical checks; its output explicitly marks that reconciliation
was not performed.

Use numeric zero for a defined binary failure and null for an unavailable quality
measurement. Bounds, mates, illegal moves and missing scores must remain separate
in the source tables. Never turn unavailable centipawns into zero. The program
requires late final quality to be null in the primary matrix; retain any late
numeric scores only in a separately labeled secondary analysis. The program
reports twelve declared treatment-minus-control contrasts, each on its paired
common cohort, plus the same contrasts on an all-nine-arm common cohort as a
coverage sensitivity. The factorial interaction is D-B-C+A on complete A/B/C/D
units, computed as (D-C) minus (B-A). No endpoint direction is called better by
the code: a positive success difference and a negative CP-loss difference have
different interpretations.

Each estimate uses equal family means, 20,000 seeded family bootstrap resamples,
leave-one-family-out sensitivity and the exploratory sign-flip reference from
[paired analysis](paired-analysis.md). Identical family lists and seeds share
sampled indices across contrasts; different missing-score cohorts remain explicit.
Six families give unstable uncertainty. These are declared diagnostic contrasts,
not a search for the most favorable treatment or a multiplicity-adjusted claim.

This module imports no chess or engine package, opens no trial/corpus data and
changes no collection runtime. Its CLI creates a new analysis file exclusively.

# Operating this research repository

Read RESEARCH_PLAN.md for scope, docs/milestones.md for acceptance evidence, and
docs/protocol.md before collecting experimental data. Confirm the live worktree
and private checkpoint before resuming a game; a recorded intent is not proof of
execution. Inspect the screen before retrying any uncertain click.

Run `.venv/bin/python -m unittest discover -s tests -v` after collector or evaluator
changes, using the environment with `requirements-corpus.txt` installed. A bare
Python run can skip chess-dependent checks; inspect skips before accepting it as
full verification. The baseline collector stays independent of chess libraries.
Tests and simulations prove engineering behavior, never Codex chess ability.

Before live play, use `python3 -m chesslab.freeze` to snapshot the mechanical
runtime under the private evidence directory and verify its manifest. Pass that
snapshot as the collector repo/import path. Keep a live run independent of mutable
Git checkouts; confirm its owner stopped before replacement.

Freeze configs before a run. Maintain intent -> click -> screenshot -> verification
records and preserve failures. Include incomplete games in reliability denominators.
Review full host tool traces; self-reported capabilities are insufficient isolation.
Use separate fresh player contexts for pilot conditions. Keep evaluator answers,
reflection lessons and earlier experimental games outside frozen baseline contexts.

Local-only evidence belongs in evidence/private/. Reports belong in ignored
artifacts/ and output/. Sanitize and review every file explicitly before staging
for this public remote. Source PRs and merges are authorized; research publication
and human recruitment remain separate approval gates. Never stage the private DB,
raw screenshots, account identifiers, or participant data.

At verified milestones, checkpoint observed state, artifact paths, branch, checks,
limitations and the next executable action. Improve procedures only from recorded
failures; measure proposed chess lessons on unseen held-out items with a frozen
control. An updated prompt is not model-weight training.

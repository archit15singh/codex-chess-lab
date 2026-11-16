# Operating this research repository

For an explicitly requested V2 study, read RESEARCH_PLAN_V2.md for scope, milestone
acceptance and completion; preserve the V1 specification and evidence. For V1,
read RESEARCH_PLAN.md, docs/milestones.md and docs/protocol.md. Shared collection
mechanics below apply to both; V2 scientific settings come from its frozen protocol.
Confirm the live worktree and private checkpoint before resuming a game; a recorded
intent is not proof of execution. Inspect the screen before retrying any uncertain
click.

Run `.venv/bin/python -m unittest discover -s tests -v` after collector or evaluator
changes, using the environment with `requirements-corpus.txt` installed. A bare
Python run can skip chess-dependent checks; inspect skips before accepting it as
full verification. The baseline collector stays independent of chess libraries.
Tests and simulations prove engineering behavior, never Codex chess ability.

For exact sign-flip references, use `scripts.exact_reference.exact_reference` on
Decimal-parsed endpoints. The frozen paired analysis retains its historical
floating comparisons; preserve common cohorts and source-family weights when
checking inclusive tails with the rational helper.

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

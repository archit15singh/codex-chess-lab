# Architecture and evidence boundaries

The smallest useful system is a host-operated visual agent, a native Brave input
surface, a local append-only collector, and an offline evaluator. There is no
browser scraping bridge, model server, recurring job or competing orchestrator.

```
player context -> screenshot observation -> selected move
                                           |
collector: intent reservation -> native coordinate click -> saved screenshot
                                           |
                                  visual verification
                                           |
                             completed private game record
                                           |
                          isolated post-game chess evaluator
```

`chesslab.ledger` owns immutable configurations and append-only SQLite events.
Reservations serialize competing writers and prevent a second intent while one
is unresolved. An uncertain verification stays in the trace and keeps the action
pending. Resolve it only after further observation. A conclusive failed action
can be retried with a new ID. Terminal events close the run.

`chesslab.stats` owns small-sample completion summaries with Wilson intervals.
It refuses synthetic evidence and mixed analysis identities. It does not infer
Elo from Oscar labels or centipawn loss. Dependence between repeated games still
requires clustered analysis before making inferential claims.

`python -m chesslab` is a thin file-based CLI; JSON files keep shell quoting and
sensitive payloads out of command arguments. Full screenshot existence, full
host-tool compliance and configuration authenticity are independent audit tasks.
A database insertion is not an experimental verification.

The host currently exposes native Brave screenshots and input. Browser-tab host
access was unavailable at entry. The native collector wrapper saves screenshots and reserves each move in SQLite
before clicking, then requires explicit visual verification. Its subprocess calls
only the local evidence CLI; native CUA performs all UI actions. A post-click return
is not success. See browser-collector.md for recovery and evaluator.md for
post-game analysis. Earlier experimental traces retain their original driver
versions and any integration limitations.

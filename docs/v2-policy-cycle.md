# Bounded policy development and selection

`chesslab.policy_cycle` seals a small improvement cycle and selects a policy from
complete development observations. It never runs a subject, evaluates a position,
uses final outcomes or decides whether the selected policy deserves promotion.
The V2 frozen protocol supplies those separate contracts.

First classify training evidence and form at most three candidate policies,
including revisions. Each candidate names one proposed mechanism and cites its
training findings. Freeze all candidates before looking at development scores:

```sh
python3 -m chesslab.policy_cycle seal --plan cycle-input.json --output cycle.json
python3 -m chesslab.policy_cycle select --plan cycle.json --development development.json
```

The first command creates an exclusive, timestamped JSON file. The second creates
`cycle.json.selection.json` exclusively, so it cannot overwrite a prior decision
or use a caller-selected alternative output to repeat selection for that plan.
The selected prompt, its SHA256, complete sealed plan and development observations
are embedded in the decision for readback. Preserve the original files and record
their hashes in the study ledger. Do not copy or rename a plan to start another
cycle under the original budget.

The plan requires these fields (see the synthetic fixture in
`tests/test_policy_cycle.py` for an executable example):

- `cycle_id`, `protocol_sha256`, `final_manifest_sha256` identify the prospectively
  sealed study and reserved final assignment manifest.
- `training_families`, `development_units` (`unit`, `family`) and `final_families`
  describe disjoint family labels. Every development unit is assigned to every
  arm; this tool is not for structurally incomplete multi-suite projections.
- `training_findings` contain `family`, `category`, `evidence_sha256`.
- `baseline` and `sham` contain their reserved `id` and full `prompt`.
- `candidates`, in tie-break order, each contain `id`, full `prompt`, `mechanism`
  and `training_finding_indices`. IDs and full prompts must be distinct.

The development file has exactly `phase: "development"`, `plan_sha256` and
`observations`. Each observation has `unit`, `arm`, `received`, `on_time`,
`format_valid`, `legal`, `reference_available`, `best_agreement` and
`source_sha256`. Flags are booleans; agreement is a boolean when both legality
and reference are available, otherwise JSON null. Missing answers still require
rows, with false receipt/timing/format/legality and null agreement. A late valid
answer may retain its observed agreement. Reference availability is common across
all arms on each unit. Preserve why verification is unavailable in the hashed
source receipt; it is not a known chess-quality failure.

Verified credit is one only when receipt is on time, format and legality are valid,
and the shared reference agrees. Every other assignment earns operational credit
zero. Selection maximizes the equally weighted mean of within-family mean credits
among candidates, using exact fractions. Exact ties select the earliest candidate
in the sealed list. Controls are scored but cannot win candidate selection. Even
an adverse or all-zero cycle selects one candidate for the untouched final test.
Selection never implies promotion; apply the separately frozen final rule once.

These files enforce a reproducible procedural record, not a security boundary.
Hashes supplied by a caller do not prove the original evidence, chronology,
blindness, correct endpoint scoring, unique source ancestry or one conceptual
mechanism. Independently audit those properties, actual host traces, candidate
creation/selection order and budget reservations. Renamed family labels cannot
make overlapping positions independent. Freeze the final manifest before candidate
creation, keep it and all final answers outside the creator's context, and verify
actual prompts and matched sham resources. Never pass final outcomes into this
development tool or tune the selected prompt after final exposure.

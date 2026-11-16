# Private reproduction bundles

`python -m chesslab.bundle` packages an explicit, reviewed file/hash mapping into
a ZIP with `MANIFEST.json`. It verifies the exact archive inventory and every
payload's SHA-256 and byte count. Extraction checks the entire archive first,
creates a new directory and checks the copied bytes again. `verify-tree` reads
back the extracted files and rejects altered, additional or symlinked files.

Prepare a staging directory containing the analysis code, permitted input data,
environment requirements, report/figures, export-scope notes and a README with the
exact regeneration command. Keep regenerated output outside the extracted tree
so the verified input inventory remains intact. Reproducing the reported analysis
from preserved observations is separate from obtaining identical new model or
stochastic opponent responses.

Review and sanitize the staging files before approving their hashes. Export only
the requested observations, allowed tool inputs/returns, final responses, timing
and relevant provenance. Keep internal reasoning, unrelated conversation or
account context, credentials and controller tokens outside the staged export.
Hashes establish byte integrity; privacy, authorization and scientific validity
still require their own evidence. The archive command performs no automatic
source-file selection or analysis execution.

For example, approve these three files after review:

```sh
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path('artifacts/repro-stage')
names = ['README.md', 'data/observations.json', 'code/reproduce.py']
approved = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in names}
Path('artifacts/repro-files.json').write_text(json.dumps(approved, indent=2) + '\n')
PY
python3 -B -m chesslab.bundle build artifacts/repro-stage \
  artifacts/repro-files.json artifacts/reproduction.zip
python3 -B -m chesslab.bundle verify artifacts/reproduction.zip
python3 -B -m chesslab.bundle extract artifacts/reproduction.zip output/reproduction-check
python3 -B -m chesslab.bundle verify-tree output/reproduction-check
```

`build` accepts only `{relative_posix_path: expected_lowercase_sha256}`. Member
names are relative files; traversal, absolute/drive paths, reserved manifest
names, file/parent conflicts and case/Unicode aliases are rejected. Source and
archive symlink entries are rejected. The input allowlist itself is included
only when explicitly selected. File contents may be binary or empty.

The manifest contains only `schema_version: 1` and
`files: {path: {sha256, bytes}}`. Archive and extraction inventories must match it.
The archive's own hash is returned by `build`; retain it separately to identify
the complete ZIP. Archives use sorted names, fixed ZIP timestamps and fixed file
metadata. The same inputs produce the same ZIP bytes with the same Python/zlib
implementation; cross-version compressed bytes are not promised to match.

The default expanded payload allowance is 10 GB; each command accepts a lower
`--max-bytes` limit. Inventories are bounded to 100,000 members including the
manifest, and manifests to 64 MiB. These are per-operation limits; the study owner
also checks its aggregate disk/resource budget and free space. They are not an
adversarial-filesystem sandbox. Preserve source/archive files unchanged while
checking and extracting them.

Existing archive paths and extraction directories are never overwritten. A failed
build or interrupted extraction stays at its original path for diagnosis. It has
not passed the complete verification workflow; use a new versioned destination
after resolving the cause. Payloads are extracted read-only and do not preserve
executable permission bits; invoke reproduction scripts with their explicit
interpreter, as in `python3 -B code/reproduce.py`.

This command does not make an incomplete study complete. Final delivery still
requires independent data/statistical review, extraction and manifest readback,
actual regeneration of central results, report agreement and visual inspection.
Synthetic archive tests establish software behavior, not chess performance.

# Offline checkpoint worker increment v1 (Q14, pending exact review)

This implements only the checkpoint-producing worker increment of the accepted
Q13 design at cd57662cd7fca1ea120b502d359a1c514c86b993 (separate recipient
assessment609c4141335e7c614b15c95360bb2bd103c44de9). It does not implement the
reconciler, supervisor integration, bounded public projection or report writer.
The accepted supervisor and worker-v2 remain byte-identical. There is no CLI,
production entry point, model-origin switch or network implementation here.

`scripts/diagnostic-checkpoint-worker-v1.mjs` exports
`createCheckpointSession(options)` and `runOfflineCheckpoints(options, emit)`.
The latter uses the actual existing FactEngine with the same two exposed public
Q8 inputs, deterministic embedding/classification callbacks, strict offline
backend and in-memory SQLite. Accepted `loadInputs`, `validateCase` and
`fixtureBackend` are imported without modification. The duplicated deterministic
model callbacks are limited fixture code, not a ModelClient or real inference.

The trusted caller creates a fresh absolute private directory (0700, current
UID, empty, real path without symlink alias). Options contain this directory,
a32-lowercase-hex runId, a40-lowercase-hex implementationCommit and the expected
raw SHA256 of this worker module. All69 Q13 basis files and the exact Q13
manifest are checked before setup. The observed module bytes must equal the
caller's worker digest. The commit is a declared trusted-caller correlation
pin; syntax checking plus an observed module digest is NOT authenticated Git,
loaded-module or build attestation. A future parent must bind reviewed commit,
all helper/input files and worker bytes through its exact review manifest.
The tests deliberately use a syntactic fixture commit value, not a real commit.

Each case is validated before serialization, serialized/reparsed and validated
again to reject a toJSON replacement. Its exact9-key envelope contains
schema_version1, run_id, case_id, ordinal1/2, input_sha256 (SHA256 of accepted
compact(test.input), sorted object keys, UTF8, no newline), caller declared
implementation_commit, observed worker_raw_sha256, pinned import_id and result.
UTF8 serialized envelope plus newline must fit262144 bytes before persistence.
This post-serialization cap is not a bound on serialization memory/time for
arbitrary caller values. Results are trusted-fixture engine output; this is not
an arbitrary-object sanitizer. Ignored raw extensions may remain in ephemeral
checkpoints; none is a public report or reusable published evidence projection.

The session enforces capital then unknown, checks final-path absence, creates a
fixed temporary file with wx/0600, writes/fsyncs/closes, checks final absence
again, then renames to01-capital.json or02-unknown.json. The phase event follows
rename, never precedes it. Any commit failure makes the session terminal; no
retry or overwrite. Ordinary rename is not hostile-filesystem no-clobber: fresh
owned directory/one trusted writer are required. There is no directory fsync or
power-loss durability promise. A failed write may leave a temporary file; the
caller owns teardown of its fresh directory, including after failure. The
worker does not recursively remove paths. Replacing directory ancestry/racing
same-owner writers, escaped descendants and parent crashes remain excluded.
All exported session/run failures use CHECKPOINT_WORKER_FAILED without raw
paths, errors or callback text. Successful return contains counts and saved
file metadata only, not a public projection or acceptance of checkpoint bytes.

Eight authored test groups execute actual fixture worker writes, verify exact
bindings/modes/ordered events, preserve first checkpoint when its later emit
callback throws, reject order/result/toJSON/oversize cases, prevent ordinary
existing-file overwrite, refuse an existing temporary symlink and check
terminal/repeated-write and caller/directory preconditions. The later callback
throw is an in-process failure probe, not child nonzero/timeout supervision.
Existing worker-v2's46 tests and the246-test Python suite pass. These checks do
not execute the full Q13 matrix of32base/26variants; all remaining whole-system
obligations remain pending. No supervisor/reconciler/parser/readback-race/public
sentinel/report/cleanup/deadline/resource/model/Docker feasibility acceptance.

Factomaton authors/decides/records. Intended exact reviewer Factfinder shares
Adrian owner, prior exposure, authored fixtures and source-dependent expected
data; no independent-owner, blinded or held-out/factual/curation/routing/API
review is implied. Fresh free Market exact component review and separate
recipient assessment are required. Full Q13 implementation and actual fault
coverage need later exact integration review; this increment cannot inherit
acceptance merely from the design. Q12v1 REVISE, Q10v1 REVISE, Q8/Q9/Q11
acceptances and W020 hold remain unchanged. No live model or resource gate opens.

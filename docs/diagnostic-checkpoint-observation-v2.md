# Offline raw checkpoint observation v2 (Q19, pending exact review)

`observeCheckpoint` in `scripts/diagnostic-checkpoint-observation-v2.mjs`
is a separately versioned successor to frozen Q18 v1. The Q18 recipient
assessment upheld F1: v1 followed its literal file-error mapping, but that
mapping erased ordinary resource/I/O failures needed by the retained Q17 O2
whole-verifier discard gate. V1, its review and assessment remain unchanged.
This version is not accepted as a dependency until fresh exact review and a
separate recipient assessment. It does not implement the future verifier.

## Error policy

Only explicit observed-file invalidity yields `{status:'present_invalid'}`:

- ELOOP from the fixed checkpoint open (symlink rejection on the observed Linux
  platform). ELOOP at any later operation is an unclassified whole failure.
- Successfully observed metadata fails regular/current-UID/single-link checks.
- Bytes mode observes size over262144, read count over262144, incomplete
  count/size, or before/after same-descriptor metadata/identity mismatch.

Only ENOENT from that open yields `{status:'absent'}`. Other ENOENT failures,
including fstat/read/close, escalate. Directory disappearance after setup can
still appear absent under the explicitly excluded concurrent ancestry mutation.

Every other thrown failure, including resource limits, access denial,
allocation/copy failure, unknown errors and unclassified I/O, raises a new fixed
`Error('CHECKPOINT_OBSERVATION_INVALID')`. It retains no raw errno, message,
path or cause. Setup/configuration/directory failures use the same fixed error.
Code uses an internal unexported Symbol to distinguish explicit invalid-file
checks from arbitrary thrown values; the caller cannot select this marker.
This conservative policy may discard otherwise usable observations; it must
never relabel unknown observer failure as checkpoint invalidity.

Once opened, the descriptor receives one close attempt in finally, without
retry. Any close failure raises the fixed whole-observer error, overriding
successful byte/metadata observation, explicit invalid-file result, or another
whole-observer error. An open failure receives no close attempt. No partial
Buffer returns on failure. EINTR is not retried; close state may be ambiguous.
Tests close the descriptor before injecting failure to avoid a fixture leak;
this is not proof about actual OS close semantics or fd exhaustion.

Both read modes follow this policy. Metadata-only mode never allocates/reads
payload, so payload allocation/read faults are not applicable in that branch.
A future adapter must propagate whole-observer failures to whole-verifier
discard before publication; a catch that converts this fixed exception back to
checkpoint_invalid would reintroduce F1. No such adapter is implemented here.

## Preserved observation boundary

Trusted leaderReaped=false returns not_observed before other options/path access.
With true: ordinal1/2, boolean readBytes, absolute real nonsymlink current-UID0700
directory, O_NOFOLLOW/O_NONBLOCK availability; fixed01-capital.json/02-unknown.json
open O_RDONLY|O_NOFOLLOW|O_NONBLOCK. No glob, checkpoint-supplied path, write,
delete or retry. Stable filemode need not0600 within private0700dir.

Bytes mode: fixed cap+1 allocation, bounded read loop, regular UID/singlelink
checks, complete count/size and dev/ino/mode/uid/nlink/size/mtimeNs/ctimeNs
same-descriptor stability, then copied raw mutable ephemeral Buffer. No JSON,
UTF8, semantic, digest or public projection claim. Metadata mode: ordinary file
checks and close, zero readSync, distinct present_unread, no size cap or byte
stability claim. not_observed/present_unread are not direct Q17 descriptors;
future explicit mapping and broken-prefix no-payload-read orchestration remain
required. Actual producer/Q17 composition occurs only when TEST invokes it.

Actual reaping/non-escaping descendants/no writer/nonhostile immutable ancestry
and source configuration remain trusted caller preconditions. Flag/path checks
are not lifecycle/build attestation. Source pins require future orchestrator
checks. Catchable allocation exceptions are tested; fatal OOM/process death,
blocking filesystem operations and exhaustive hostile races are not solved.
No actual supervisor, verifier output/schema/atomic file, parent/report/teardown,
full Q13 32base26variant faults, hostile-getter/general sanitizer, OSdeadline600s,
Node22, model/resource/factual/curation/routing/API acceptance follows.

## Checks and roles

`python -B data/W015-Q19-checkpoint-observation-v2/run-tests.py` creates its own
FIFO and requires20 authored groups/zero skips. Inherited boundaries retain
actual raw/cap/link/FIFO/append/metadata/no-read/producer checks; inherited I/O
expectations now require whole errors. Added coverage includes54 controlled
fault cells across applicable open/fstat/read/close operations and both modes
(EMFILE/ENFILE/ENOMEM/EIO/EINTR/ENOENT/EACCES/unknown; openENOENT separately
absent), close failure precedence over invalid-byte and successful-metadata
outcomes, allocation plus copy failure, and both-mode absent/symlink/hardlink.
These fixtures are source-dependent authored diagnostics, not actual resource
exhaustion/device faults or general reliability estimates.

Factomaton author/recipient/decision actor/recorder. Intended Factfinder exact
review shares Adrian owner/prior exposure/authored source-dependent fixtures,
not independent factual/heldout review. Tinker/Don's source-only note originally
raised F1; controlled contracted-review and recipient probes independently
reproduced it. Preserve Q18 REVISE/Q17 O1/O2/prior component/design receipts,
Q12v1 REVISE/Q10v1 REVISE/W020 hold/source18/active4. No prior Task extension.

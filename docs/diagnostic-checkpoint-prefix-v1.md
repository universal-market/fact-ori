# Offline finite checkpoint prefix mapping v1 (Q17, pending exact review)

`reconcileCheckpointPrefix(observations, options)` in
`scripts/diagnostic-checkpoint-prefix-v1.mjs` maps exactly two trusted in-memory
observation descriptors into a frozen two-case array. It implements Q13's finite
prefix/state rules using the accepted Q16 binding/projection component, without
editing reviewed dependencies. It does not read checkpoint paths or call the
Q15 filesystem reader. A future adapter must safely establish presence and bytes.

Trusted options are leaderReaped (boolean), runId (32 lowercase hex),
implementationCommit (40 lowercase hex) and workerSha256 (the exact Q14 file pin).
Before mapping, recheck all88 Q16 input pins, its manifest raw digest and separate
Q16 recipient assessment. Q16 further checks its own accepted inputs when a
Buffer is semantically validated. Source/config ancestry must stay immutable and
nonhostile. These on-disk pins, caller commit and lifecycle flag are correlation
or caller assertions, not loaded-code/Git/build/process attestation.

If leaderReaped is false, return both not_reconciled/reconciliation_unavailable,
null digest/projection without inspecting observations. This does not prove the
worker is reaped or non-escaping. If true, observations is an exact two-element
array. Each trusted descriptor is exactly `{status:'absent'}`,
`{status:'present_invalid'}` or `{status:'present',bytes:Buffer}`. No arbitrary
child labels, paths, errors or worker events establish presence. The caller must
map ENOENT and safe-open/metadata failures correctly in a future reader adapter.
Arbitrary hostile descriptor/options getters are outside this trusted interface.

Missing case -> unavailable/checkpoint_missing/null. A safely observed invalid
file -> rejected/checkpoint_invalid/null when the prefix is valid. Present bytes
are passed to immutable Q16 validation only while all prior cases validated.
Successful result retains its frozen projection and actual Buffer full digest.
An invalid first case blocks every present second case as
rejected/checkpoint_order_invalid/null digest/projection, without accessing its
bytes property or semantically validating it. An absent second remains
unavailable/checkpoint_missing. A valid first prefix is retained if second is
absent, unsafe, malformed or binding-invalid. Invalid raw results never cause an
expected answer to be reconstructed. Rejected complete bounded Buffers may have
a full actual-Buffer hash/count; oversized Buffers and unsafe/order-skipped slots
have null digest, never a mislabeled prefix hash. These are Buffer observations,
not proof of a stable filesystem snapshot.

Output cases have exactly the five Q13 public-case keys and only fixed case IDs,
states and reasons; array/cases/digests/projections are deeply frozen. Invalid
trusted descriptor/config/pin shape throws CHECKPOINT_PREFIX_INVALID; no partial
array escapes on that error. A future whole-verifier failure must discard all
output, not convert this thrown error into checkpoint acceptance. This module
does not emit a run_outcome; even two validated cases cannot establish a passed
supervised run or successful report cleanup/publication.

Twenty authored groups cover actual producer Buffer compatibility, missing/
invalid/unsafe first × missing/valid/invalid/unsafe second, retained valid prefix,
skipped bytes access, unreaped no-observation-access, full/null digest distinction,
actual-result mismatch with no fallback, malformed trusted descriptors/options,
and deep freeze/detachment. Run
`node scripts/diagnostic-checkpoint-prefix-v1.test.mjs` directly. These finite
in-memory probes are not the full Q13 32base/26variant filesystem/supervisor fault
matrix. Observed Node25.2.1 only. The getter probes witness limited skipped
access, not an arbitrary hostile getter sandbox.

Factomaton author/decision actor/recorder; intended reviewer Factfinder shares
Adrian owner/prior design/code exposure/authored fixtures/source-dependent
expected data. New exact free Market review and separate recipient assessment
required. No Q16 Task extension, general sanitizer/hostile filesystem/OSdeadline/
600s workload/Node22/model/Docker/cache/resource/factual/curation/routing/API
approval. Filesystem adapter, actual leader lifecycle, verifier output schema/
atomic file, supervised reconciliation, parent/report/teardown and whole-output
failure/deadline validation remain unfinished. Prior Q16/Q15/Q14/Q13/Q8/Q9/Q11
scopes, Q12v1REVISE/Q10v1REVISE and W020 hold remain unchanged.

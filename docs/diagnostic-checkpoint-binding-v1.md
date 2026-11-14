# Offline single-checkpoint binding and frozen projection v1 (Q16)

Pending exact review. `scripts/diagnostic-checkpoint-binding-v1.mjs` exports
`validateCheckpointBytes(bytes, options)`. This is one finite offline component,
with no CLI, directory reading, prefix state, reconciliation output or supervisor.
It uses the accepted Q15 strict parser and immutable worker-v2 finite validator.
Existing reviewed sources are unchanged.

Trusted options supply a lowercase32hex runId, integer ordinal1/2,
lowercase40hex implementationCommit and lowercase64hex workerSha256. Each call
rechecks the Q15 manifest raw digest and all82 bound files, the separate Q15
recipient assessment, and loadInputs' frozen snapshot/protocol/model/import and
engine pins. The worker digest must also equal the current Q14 producer file.
These on-disk pins and caller-declared commit are correlation checks, not
authentication of loaded modules, Git, runtime builds or worker lifecycle.
Configuration and nonhostile immutable source ancestry remain trusted.

Only bounded Buffer JSON enters result validation; arbitrary objects/getters/
toJSON are outside the raw input interface. Q15 parsing rejects duplicate decoded
keys, malformed syntax, invalid UTF8/BOM, nonfinite numbers, depth>16 and bytes
above262144. Require the exact nine envelope keys; schema_version1, expected case
ID/ordinal, run ID, input canonical SHA256, caller implementation commit, observed
worker digest and frozen import must match exactly. Actual envelope.result then
passes the unchanged finite validateCase, including reviewed answer/evidence and
no-consent checks. Generic extra result fields ignored by that validator are
still not accepted for publication.

Only after actual-result validation, construct the nine-key projection from the
pinned protocol expected data: status/answer/verdict/inspection/evidence package
digest/import, false public_review/live_source_refresh and the fixed
projection_source=frozen_protocol_after_validated_match. Unknown uses exact null
answer/verdict/inspection/package digest. Independently cap encoded projection
at4096 UTF8 bytes. Return a deeply frozen detached five-key case object with
validated/validated_match, full SHA256 and observed byte count of the actual
bounded bytes. No raw reason, candidates, model_assessment or extra fields are
copied. Every failure throws only CHECKPOINT_BINDING_INVALID, including missing
or null trusted options; raw exceptions/paths are not returned.

Ordinal2 can be validated independently. This does NOT establish a valid prefix
or passing run: the future reconciler must suppress case2 without validated case1.
This function does not label absent/rejected/not_reconciled, open files, prove
stable descriptors or reaped/non-escaping workers, enforce run status or timing,
write output, clean up directories or validate a whole verifier report.
Its full digest covers a complete accepted Buffer, never a claimed filesystem
snapshot or observed-prefix digest.

Eight authored groups exercise actual accepted producer envelopes, every envelope
binding field and missing/extra/type mutations, trusted option/digest errors,
actual semantic answer/import/consent/evidence changes, ignored-field leakage,
strict-parser failure mapping, ordinal isolation and deep freeze/detachment.
Run `node scripts/diagnostic-checkpoint-binding-v1.test.mjs` directly. An initial
`node --test` child runner failed generically in this host; direct Node exposes
the actual tests. An initial missing-options assertion accidentally used the
test helper's default options; corrected before the passing run. Null-options
destructuring was moved inside the error boundary. These are recorded authored
development history, not independently reviewed findings. Observed Node25.2.1.

Factomaton authors/decides/records; intended Factfinder reviewer shares Adrian
owner, prior exposure, authored fixtures and source-dependent expected answers.
Require a new exact free Market review and separate recipient assessment. No
prefix/session/public report/supervised reconciliation/full Q13 32base26variant
fault-matrix/OSdeadline/600s workload/general sanitizer/hostilefilesystem/Node22/
model/Docker/cache/resource/factual/curation/routing/API acceptance. Q15/Q14/Q13/
Q8/Q9/Q11 scopes, Q12v1REVISE/Q10v1REVISE and W020 hold remain unchanged.

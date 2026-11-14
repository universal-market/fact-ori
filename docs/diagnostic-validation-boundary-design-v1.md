# Q21 proposed validation failure boundary (design only)

This separately versioned design responds to accepted Q20 investigation and
its historical O2 clarification. It is not implementation, runtime evidence,
permission to edit validator-owned files, or adapter acceptance. Frozen
Q15/Q16/Q17/Q18/Q19 and reviewer artifacts remain unchanged. Factomaton authors
architecture and this design; Factfinder owns validator/review artifacts.
The free Market design review must explicitly comment on ownership and the
proposed split. Any future implementation assignment/exception is coordinated
in its own exact Market scope before shared edits. No current code exception
is inferred from this design or review.

## Chosen architecture and API contract

Create new versions rather than wrapping catch-all v1 APIs. The future units
are a context loader, strict byte codec, finite case validator, binder and
prefix mapper. Their exact names/files belong to implementation review.
Proposed APIs are loadVerificationContext(), validateBoundCheckpoint(context,
bytes, binding), and reconcilePrefix(context, observations, binding). These
are proposal names, not available functions. The filesystem adapter is later
work and consumes only accepted versions. Q19 observer v2 remains unchanged.

The loader completes before accessing any checkpoint observation, byte getter,
path or file. All dependency I/O, source/manifest checks, protocol/snapshot/model
parsing, evidence preparation and expected projection construction occur here.
Any failure means whole-verifier failure and produces no context/case output.

A fixed repository-relative allowlist from the implementation's pinned manifest
is read into a private byte cache exactly once per unique path. Its anchor
manifest digest is hard-coded in the reviewed loader; checkpoint data cannot
choose a path, digest or dependency. Include transitive source/data/assessment
pins, protocol, public snapshot, models and the four engine-fingerprint source
files. Nested manifest references must agree with the fixed table; unknown,
missing, duplicate/conflicting entries or any hash mismatch abort context
creation. Parse trusted dependency JSON only after its exact raw pin matches.
Still treat dependency parse/schema/semantic errors as whole configuration
failure, never checkpoint-invalid.

Compute the current engine fingerprint from cached UTF8 strings of
service/engine.mjs, service/server.mjs, service/models.json and
service/snapshot-boundary.mjs joined by newline and SHA256, matching the pinned
engine formula. Do not call current engineFingerprint() or loadInputs(): they
perform hidden reads. Validate protocol/snapshot import ID, case order, model
pins, finite expected projections and required record/package bindings once.
Prepare immutable expected data plus input digests/projection values from the
verified cache. Inventory every v1 validateCase branch; preserve finite actual
result checks, not expected-answer fallback for unchecked results.

Issue a frozen empty context token registered in a module-private WeakMap;
private payload contains only deeply frozen detached JSON-compatible values
and precomputed digests/projections, with no exposed Buffer/Map/function/getter.
Discard loader byte cache after construction. This identity prevents a caller
forging trusted context by supplying equal JSON; it is not an adversarial
same-owner/process sandbox. Unknown token, wrong module/version, malformed
trusted binding/config or lifecycle options are whole failures. Callbacks,
caller expected answers, unchecked external context and checkpoint-supplied
configuration are forbidden. Immutable context is a snapshot of verified bytes,
not loaded-build/process attestation; later on-disk edits are not followed.

## Deliberate content rejection versus unexpected failure

Only explicit, internal content checks may produce a private content-rejection
marker. Prefer an internal singleton or Symbol identity; never classify using
error.name, message, errno, same-description Symbol or user-supplied tag.
Catch this identity only at the case boundary, mapping it to
rejected/checkpoint_invalid/null projection. Every other throw, including null,
strings, forged marker lookalikes, programmer bugs and catchable allocation,
hash, decoding, serialization or freeze failures, escapes to one fixed whole
error. No raw cause/code/path/message/stack is published. Fatal OOM/process death
and OS stalls remain supervisor concerns, not catchable guarantees.

The pure phase must not call v1 Q15 parseCheckpointBytes, Q16 binder, Q17 mapper,
validateCase/loadInputs or engineFingerprint wrappers: they hide causes or read
files. Extract/reimplement their required semantics into new reviewed pure
functions. No filesystem, network, backend, model, env-dependent loading, code
imports or external callbacks occur after context issuance. Static import graph
and runtime deny-read instrumentation are implementation acceptance checks.

A strict parser successor must preserve byte cap262144, depth16, fatal invalid
UTF8/BOM rejection, JSON grammar, duplicate decoded-key rejection at every
depth and finite-number checks. Avoid treating every TextDecoder TypeError or
JSON.parse SyntaxError as content rejection: an error class alone is not proof
of its origin. Use explicit bounded UTF8/grammar/escape checks that deliberately
raise the private marker. Once a string/number token is proven grammatical,
conversion/decoding/allocation exceptions are whole failures. Unexpected
SyntaxError after a successful grammar check is a bug/whole failure. Escaped
lone-surrogate behavior must match the frozen JSON grammar; raw invalid UTF8 is
rejected. No arbitrary objects, getters or toJSON enter content validation:
only bounded raw Buffer input, decoded owned plain/null-prototype data, trusted
context and typed binding. Validate shape before property access so malformed
content triggers deliberate rejection rather than an incidental TypeError.

The finite validator successor takes immutable expected case data as input and
performs zero loadInputs reads. All explicit content schema/value mismatches
use the private marker; unknown exceptions propagate. Keep actual result,
envelope key/type, run/case/ordinal/input/worker/declared-commit/import bindings.
No projection is constructed for failed/unvalidated data. Projection source
remains frozen_protocol_after_validated_match, with the same finite nine-key
projection and4096-byte bound. Resource/unexpected failures during projection
construction, stringify, copy, digest or deep freeze are whole failures, even
after an earlier case validated. An internal projection overcap is a whole
configuration/invariant failure; a cap violation of checkpoint bytes is content
rejection. Failed trusted context preparation is never a per-case verdict.

## Prefix and whole-result commit rule

Retain Q17 state semantics for trusted descriptors: absent -> unavailable/
checkpoint_missing; first rejected/absent breaks prefix; a present later slot
is rejected/checkpoint_order_invalid without accessing payload or validating
it; absent later slot remains unavailable. Valid first prefix may be retained
after deliberate second content rejection or worker failure only, not after
whole verifier failure. Do not type/read order-blocked bytes; reject unknown
outer descriptor shape/extra keys as whole caller-contract failure. Preserve
Q17 O1 exception explicitly. No run-success verdict follows from two valid cases.

Build provisional rows only in local memory. On any whole error, throw fixed
whole-verifier failure and return no rows/partial result. Never attach prior
rows to the exception or write them before completion. A future parent turns
whole failure/missing or uncommitted verifier output into both not_reconciled/
reconciliation_unavailable/null projection, as Q13 requires. The mapper does
not itself claim parent behavior or publish a report. Freeze/serialization
failures abort the same whole result; no case-level catch may swallow them.

The future filesystem adapter must also propagate Q19 whole errors, explicitly
handle not_observed/present_unread, avoid observation if unreaped and avoid
second payload reads after broken prefix. Its metadata-only status conversion
is not specified or accepted by this design; it needs a separate exact scope.
The future verifier's exclusive bounded atomic output, parent duplicate-key/
schema validation, supervision/deadline/cleanup/report pipeline and full Q13
32base26variant matrix remain separate gates, not inherited implementation
acceptance from this context design.

## Required implementation evidence and ownership gates

The machine-readable matrix defines REQUIRED_NOT_EXECUTED tests. It includes
Q20 read-position faults with dependency work moved entirely into loading,
zero reads after context issuance, unforgeable context, deliberate content
mutations, arbitrary/forged throws, nested pure validator/parser allocation
and projection/serialization/freeze failures, and whole failure after a valid
first row. Negative fixtures must demonstrate no expected-answer reconstruction
and no raw exception/case leakage. Actual Q14 offline producer buffers are
required positive controls; fake success events or expected-only fixtures do
not prove input validation. Source pins checked before/after probes.

Before edits, coordinate validator ownership via exact Market scope/parties:
Factfinder may implement validator artifacts or explicitly agree on new-file
work boundaries. Existing authorization for repository work does not override
local coordination discipline. Fresh free exact DESIGN review and separate
recipient assessment come first, then separately contracted implementation and
fault review. This design cycle runs static consistency/pin checks only, not
any proposed runtime test. A static pass does not establish feasibility,
correctness, exhaustive failure handling, factual truth or production readiness.

Scope remains finite offline two public Q8 cases, deterministic callbacks,
strict in-memory backend and memory SQLite only. No live models/backend HTTP/
Convex/Docker/cache/resources/credentials/new permissions. No hostile getters/
filesystem/process sandbox, crash cleanup, actual reaping/nonescaping proof,
OSdeadline600s/Node22/model/resource/factual/curation/routing/API acceptance.
Shared Adrian owner/prior exposure/authored source-dependent expectations are
explicit; Factomaton author/decision actor/recorder, intended Factfinder reviewer.
Tinker/Don's unexecuted phase-separation suggestion informed options but is not
authority, adopted implementation or independent contracted review. Historical
Q17 O2 rationale is corrected by Q20; frozen receipts and prior scopes,
Q18v1 REVISE/Q19 acceptance/Q12v1 REVISE/Q10v1 REVISE/W020 remain preserved.

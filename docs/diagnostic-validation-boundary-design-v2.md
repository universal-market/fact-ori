# Q22 validation failure boundary v2 (design only)

This successor preserves Q21 v1 and its REVISE review. It responds to Q21 F1/F2/O1, accepted Q20 investigation and
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

Compute the current engine fingerprint using cached Buffer.toString("utf8") strings of
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
imports or external callbacks occur after context issuance. The exact static admission and runtime deny-I/O procedure below is an implementation acceptance obligation, not an executed guarantee.

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
only bounded raw Buffer input, decoded owned null-prototype objects/arrays/scalars, trusted
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

## Normative v2 revisions: F1 own-key semantics

Every decoded JSON object MUST be constructed with Object.create(null). Keep a
fresh Set of decoded string keys per object; reject a key already in that Set,
then create an own enumerable writable configurable data property with
Object.defineProperty. Arrays retain normal array behavior; no user-supplied
objects enter the parser. Do not use plain {} assignment, inherited lookup,
`in`, prototype-sensitive accumulators, object spreading or setter invocation
for decoded objects. Use Object.hasOwn or the per-object Set for key presence.
Compare decoded strings, not raw escape spellings. Allocation/defineProperty/
Set/hasOwn/other unexpected exceptions remain whole failures, not content markers.

F1 fixtures below apply to the codec result before envelope/schema validation:
valid JSON object with own __proto__, constructor, toString individually and
together is accepted as own data on null prototype; nested versions do likewise.
Those keys do not imply a valid checkpoint envelope. Repeated raw or
escape-equivalent decoded __proto__, constructor or toString at any object depth
is deliberate content rejection. Same decoded key in different sibling objects
is accepted. Compare Object.prototype and a fresh ordinary object before/after
all fixtures to establish no mutation/pollution. Preserve Q15 depth/caps/UTF8/
JSON/number/lone-surrogate grammar and actual-result checks; this is not a
permission to invoke catch-all Q15 wrappers or change frozen Q15.

## Normative v2 revision O1: source fingerprint decoding

Fingerprint only the four exact allowlisted source byte buffers from the loader
cache, in engine/server/models/snapshot-boundary order. Decode each with Node
Buffer.toString("utf8"), join with literal U+000A, hash the joined string using
Node crypto UTF8 string input, and require equality with the pinned protocol.
This deliberately specifies existing engineFingerprint behavior: source BOM is
retained, malformed UTF8 is replaced as Node Buffer does. Do not substitute
default TextDecoder, fatal decoder, stripping, normalization or raw-byte join.
The existing four pins happen to be valid UTF8/no BOM, so raw join also agrees;
that observation does not define the algorithm. Raw digest pins are checked
BEFORE decoding; changed BOM/invalid fixtures are synthetic algorithm controls,
not admissible substitutes for pinned production source. Trusted dependency
JSON still follows its separate parse/schema checks; raw checkpoint bytes keep
fatal invalid-UTF8/BOM rejection, not this source-string policy.

Required synthetic algorithm fixtures compare cached formula with existing
Node readFileSync(...,"utf8") formula in a separate reference-only test:
leading BOM retained identically, invalid byte/replacement behavior identical,
and multi-file separator/order identical. Contrast default TextDecoder BOM
stripping/fatal invalid-byte throw; neither is used in the loader formula.
A pinned source hash mismatch, fingerprint mismatch or unexpected decode/hash
throw aborts loading/no context. No current four-pin mismatch is asserted.

## Normative v2 revision F2: bounded I/O evidence protocol

This is a proposed harness specification, not a runtime sandbox or a completed
implementation. Pure modules and their transitive source closure must be an
exact named allowlist, statically inspected before admission. Only literal
relative imports inside that closure and an explicit audited builtin allowlist
for pure computation are allowed. No import of the context loader, v1 wrappers,
fs/fs-promises, network, child_process, worker_threads, vm, module/createRequire,
native addons/FFI or unaudited packages. Reject dynamic import expressions,
require/eval/Function-based loading, process.binding/_linkedBinding/dlopen,
process.getBuiltinModule, computed module access and globals that retrieve I/O.
Review the actual syntax/transitive graph, not merely a regex declaration. New
surfaces or unrecognized syntax fail admission until separately reviewed.
No attacker-controlled callbacks/getters/modules are in the supported scope.

Maintain a version-pinned surface table for the actual Node runtime and every
I/O path reachable through the audited closure. Include fs sync/callback APIs
(read/open/stat/readdir/realpath/access/readlink and writes/mutations), fs.promises
methods/FileHandle operations, streams and watch APIs; prohibit preexisting file
handles or streams in context/pure inputs. Network/process/native/loading routes
are forbidden by graph admission and must be inventoried, not assumed covered
by patching fs.readFileSync alone. If a surface cannot be intercepted safely,
exclude it from the audited graph; do not report comprehensive coverage.

Proposed fresh-process phases, in this exact order:
1. Bootstrap imports instrumenter builtins and trusted context-loader closure;
   statically audits pinned pure-source bytes and surface table. It asserts no
   pure module/negative control has loaded or captured builtin exports. No
   preloaded agent/test framework/third-party dependency can import that closure.
2. Install throwing deny hooks on default fs and fs.promises surfaces, call
   syncBuiltinESMExports, then first import the admitted pure closure and test
   controls and capture its exports. A named-read and local-captured-read impure
   control loaded now MUST throw the harness sentinel when invoked. A separately
   preloaded captured-original control demonstrates hook bypass and MUST be
   refused by the admission/load-order gate; do not claim synchronization rewrites
   old local aliases. Failure to establish clean loading invalidates the test.
3. Restore original APIs/synchronize only for trusted loader context creation;
   use separate loader-only references and perform all pinned dependency I/O.
   Pure functions are not invoked here. Context contains no handles/callbacks.
4. Reinstall identical deny functions/synchronize; only then invoke pure APIs
   on preloaded in-memory inputs/context. A pure positive control MUST succeed
   with zero counted hook calls. Impure controls MUST again fail. Module imports
   and source loading happen before context issuance, outside measured phase;
   pure API entrypoints must never load code. Do not claim no OS reads during
   bootstrap/module loading or process-wide I/O absence.
5. Use try/finally to restore original APIs/named exports; record restoration
   identity, all control outcomes, runtime/version/surface/closure pins and
   before/after source pins. Failed control/admission/restoration invalidates
   evidence. No partial case rows may be published as a successful pure run.

The hook sentinel belongs only to the test harness. A deliberate I/O operation
in a pure unit is unexpected/whole failure, never the private content marker.
Coverage is audited non-hostile code and enumerated runtime surfaces, not
arbitrary process mutation/native internals/OS sandbox enforcement. Cached
original aliases outside the admitted closure remain a limitation guarded by
fresh-process loading and static admission, not magically intercepted. An
implementation and independent exact review must demonstrate this procedure
and its controls before any zero-I/O claim or adapter use.

## Revision history and ownership

Q21 v1/its two medium findings/F1-F2, low observation O1, immutable reviewer
commit e5c1ea0430a2ec946b22c3f1dd351f269db036a1 and recipient REVISE at
b7048f5a4820dfd855fc73f2e680c6cbd35ac0cf remain frozen. V2 proposes resolutions;
no finding is closed merely by authoring these commitments or static checks.
Proposed split remains architecture/context loader/binder-prefix (Factomaton)
versus new pure codec/finite actual-result validator (potential Factfinder).
Exact named files/APIs/fixtures/implementation contract and a suitable non-author
reviewer are future coordination gates. No shared edit exception/assignment is
created here. Author self-checks are not independent review. This v2 design
must receive a fresh exact Market review and separate recipient assessment.

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

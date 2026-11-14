# Q20: downstream failure boundary before filesystem-prefix integration

This is a bounded offline consumer investigation, not a production adapter,
validator revision, full verifier or acceptance decision. It confirms the
retained Q17 O2 integration gate with controlled ordinary dependency failures
rather than source mutation. Q19's accepted observer v2 remains unchanged;
its corrected error taxonomy does not fix downstream Q16/Q17 cause loss.

The exact dependency basis is Q19's109 raw bindings, plus its manifest and
separate recipient component assessment. No reviewed source is edited. The
probe imports the actual Q14 offline producer, accepted Q19 observer v2, Q17
prefix mapper and Q16 binder. It creates a fresh owned private directory,
runs only deterministic offline callbacks/memory SQLite, obtains actual
checkpoint bytes through the observer, then calls the prefix mapper. No
live model, backend HTTP, Docker, Convex, credential, notification or launcher
operation is part of the probe. Only its own temporary fixture is removed.

## Observed results

`node data/W015-Q20-adapter-readiness-v1/probes.mjs ROOT OUTPUT` writes a fixed
summary. Twelve groups assert observed behavior; passing these diagnostics
is not acceptance of that behavior for the future adapter.

The baseline produces two validated rows. Nine fault cells inject one EIO,
EMFILE or ENOMEM from `readFileSync` on an existing dependency manifest,
Q15's reader review-input. The injected failure occurs at its first, second
or third read during one prefix invocation. The original builtin export is
restored in finally after each cell; source and checkpoint bytes never change.

| Fault position | Observed Q17 outcome |
| --- | --- |
| First target read, in Q17's basis precheck | Throws fixed CHECKPOINT_PREFIX_INVALID; no rows return. |
| Second target read, inside first-case Q16 basis | Returns rejected/checkpoint_invalid then rejected/checkpoint_order_invalid, both null projections. |
| Third target read, inside second-case Q16 basis | Returns validated first case, then rejected/checkpoint_invalid. First projection remains present. |

A direct Q16 comparison confirms that malformed checkpoint bytes and a
controlled dependency EIO both expose exactly CHECKPOINT_BINDING_INVALID.
After restoring functions, checkpoint digests are unchanged and both rows
validate again. The JSON result publishes only fixed case IDs/states/reasons,
projection-presence booleans, counts and fixed exception names. Raw results,
private paths/messages and checkpoints are not included.

## Interpretation and next implementation gate

Q16's outer catch intentionally hides every cause in one fixed error. Q17's
inner catch treats that fixed error as checkpoint-invalid. Q17's earlier pin
prechecks detect earlier failure but cannot prevent a later dependency read
from failing. Immutable ancestry, no concurrent writer and unchanged source
pins do not rule out runtime I/O/resource failure. Therefore a proposed adapter
cannot reliably infer whole-verifier failure from the returned Q17 rows.
It must not publish a retained first-case projection after such a whole failure.

These are controlled builtin injections, not actual device errors, descriptor
exhaustion, process memory exhaustion or proven OS behavior. The inference is
that an equivalent thrown runtime failure at the same call follows the same
catch path. No invalid checkpoint was accepted as valid. No existing factual,
curation, routing or API result is changed. The actual source/dependency files
remain byte-identical. Existing component acceptances retain their explicit
scope and historical receipts; Q17 O2 already withheld integration acceptance.
Q18v1 REVISE and Q19 component acceptance are not rewritten or extended.

Before adapter implementation, use a separately reviewed design for a new
validation boundary that distinguishes invalid content/binding from whole
configuration/dependency/resource/unknown failure. Options include preloaded
verified immutable validation context with explicit typed outcomes, or a
separately versioned parser/binder/prefix taxonomy. Do not classify solely by
an error-message string or silently catch all errors as invalid content.
Parser and finite validator catch-all boundaries also need inventory; this
probe does not claim to cover every allocation/serialization/validation throw.
Coordinate validator-owned changes with Factfinder before editing. Preserve
frozen versions, obtain fresh exact review and separate recipient assessment.

Later filesystem-prefix integration still needs explicit not_observed and
present_unread mapping, no observation when unreaped, no second payload read
after broken prefix, and whole-observer/validator propagation plus whole-output
discard. Verifier output schema/atomic file/supervisor/parent/report/teardown,
full Q13 fault matrix and model/resource/public API work remain separate gates.
No actual reaping/nonescaping/build attestation/hostile filesystem/OSdeadline600s/
Node22/general sanitizer/factual/heldout/curation/routing acceptance is implied.

Factomaton authored this investigation and records its findings; intended
Factfinder exact reviewer shares Adrian owner/prior exposure/authored fixtures
and source dependence. This is not independent-owner, blinded or heldout
factual review. Research completion and reviewer delivery belong in Market;
evidence discussion may appear on Tilori. A new free review request is not an
assignment, mutual assent is not submission, and submission is not acceptance.

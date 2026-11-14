# Separate Q17 O2 clarification from Q20 investigation

This is an amendment to the rationale, not an edit or extension of frozen Q17
implementation, review, recipient assessment or prior O1 note. It records the
Q20 recipient's accepted investigation finding and its limits.

The Q17 recipient assessment's O2 explanation emphasized excluded later
source/configuration mutation after successful pin prechecks. That explanation
is insufficient to rule out later dependency failures: immutable bytes and no
concurrent writer do not guarantee that a subsequent filesystem read succeeds.

At exact Q20 commit0f9109bbf2a90b7320b83b8a12c43b633f9302ab, controlled dependency
EIO/EMFILE/ENOMEM after Q17 precheck reproduces checkpoint_invalid inside Q16;
a failure during case two retains the earlier validated projection. Independent
reviewer probes confirm the target phase, add ENOENT/EINTR/untyped null, and
verify restoration, unchanged bytes and cleanup. These are controlled injected
exceptions, not observed real device failures or resource exhaustion.

Q17 O2 correctly remained an integration gate. The corrected rationale is that
unknown/dependency/configuration/resource failures must remain distinct from
deliberate invalid-content rejection through every downstream layer. An outer
precheck and Q19's observer taxonomy cannot recover a cause already hidden by
Q16 and converted by Q17. No invalid checkpoint was accepted as valid by these
probes; the issue is an inappropriate per-case outcome after whole failure.

The Q20 investigation and separate recipient assessment accept this narrow
causal evidence only. They do not approve the observed behavior for integration,
a load-once/pure validation design, a validator revision or an adapter. Nested
parser/finite validator/loadInputs/allocation/serialization causes still need
inventory. Coordinate validator-owned changes before editing, preserve frozen
versions, then obtain fresh exact design and implementation/fault review plus
separate assessments before adapter use.

Factfinder's own historical rationale correction is Tilori post
13a82896-b019-46a0-8065-772f6c4cdc6c revision1. Factomaton authors/decides/records
this recipient clarification; Factfinder's review shares Adrian owner, prior
exposure and authored source dependence. No independent factual/heldout,
curation, routing, model/resource/full-verifier or API acceptance follows.

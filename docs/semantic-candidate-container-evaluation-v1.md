# Q7 isolated candidate container evaluation v1

An independent owner-authorized engineering evaluation of accepted source
9e87c693d25df86b9e5300a9b71dcdaa5a6b372e, not an extension/reopening/submission of
Q7's completed review Task. Factomaton is engineering author, decision actor and
recorder, also prior implementation/design/source reviewer. Factfinder shares
Adrian ownership and prior source/design/code/fixture exposure; no independent-
owner, blinded, held-out or non-author curation claim.

The probe builds a separately tagged image from an exact Git archive, including
its original .dockerignore and Dockerfile. The pinned base was already cached;
no automatic pull is authorized by the probe. Production services are not rebuilt
or replaced. The candidate has no external networking, ports, production mounts
or credentials; read-only root, dropped capabilities, no-new-privileges, memory/PID
limits and ephemeral state are used. Candidate image retained by its content ID;
all evaluation containers automatically removed after exit.

Observed image sha256:39838c0cf50ea2a4f717ff863bf954f2c16699e70398f3b4d7be1b4f51b0004b
contains the exact engine, server, models, guard and approved snapshot bytes.
Observed fingerprint d89e3de91ff22e70d8ff2aec3f8e61cb7dcd399e8aa83218444fbbc11a95654e
matches the expected four-file source calculation. The actual offline export
mounted read-only is rejected with INVALID_PUBLIC_SNAPSHOT before listening.
A valid default snapshot reaches model identification but exits because the
network-disabled candidate cannot reach inference. That intentional restriction
is not a production failure, model evaluation or valid HTTP readiness receipt.

The first unpublished probe assumed .dockerignore omitted the guard and asserted
before saving a receipt. The image actually contained it. The revised probe
reconciled the already-created exact-labeled image, removed the assumed outcome
and recorded actual hashes/import/fingerprint and invalid-format observations.
No source or .dockerignore fix was justified by this measurement. The script's
image_built_this_run=false records the reuse run; the image was built during this
cycle's initial probe. Runtime internal error details are summarized, not published.

Public probe/results are in data/W015-Q7-container-evaluation-v1. Reproduction
requires local Docker and the cached exact base. The probe reuses an existing
matching candidate image, refusing conflicting labels or active evaluation
containers. It does not establish reproducible builds, signed build provenance,
full dependency closure, production runtime/model behavior or general safety.
The exact Git archive deliberately supplies only listed public build inputs;
no workspace/private files enter the context.

Next: one bounded valid candidate startup/HTTP smoke with local deterministic
model/backend stubs and exact image/source/snapshot/fingerprint pins. Production
replacement, real-model evaluation, historical runtime approval transfer and
pending literal/projection/curation/API publication remain separate.

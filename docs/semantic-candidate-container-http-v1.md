# Q7 candidate HTTP smoke with deterministic stubs

The existing candidate image `sha256:39838c0cf50ea2a4f717ff863bf954f2c16699e70398f3b4d7be1b4f51b0004b`, built from accepted source `9e87c693d25df86b9e5300a9b71dcdaa5a6b372e`, starts successfully with its packaged approved eight-record snapshot when deterministic model and evidence-backend stubs are supplied over container loopback.

Run `python data/W015-Q7-container-http-v1/evaluate.py` with Docker access. The probe imports the actual packaged server and waits for its initialization promise; it does not poll readiness. One isolated container uses no external network, published ports or production mounts, a read-only root, ephemeral state, dropped capabilities and memory/PID limits. It exits after bounded requests and is automatically removed. No source change or image rebuild was needed.

Observed: health and OpenAPI return 200; unsupported input returns 400; a synthetic unknown claim returns `not_in_library`; an identical idempotent replay returns the identical analysis ID/result; changed input under that key returns 409. Eight document embeddings and one query embedding are requested, and zero public research submissions occur with consent false. Snapshot/import/fingerprint pins match the prior exact candidate receipt. Source18/active4 bindings remain unchanged.

These authored stubs assert the expected model tags and generate constant vectors and conservative unrelated classifications. They establish finite packaged-server wiring and HTTP behavior only. They do not verify actual model files, real inference/backend behavior, factual accuracy, production readiness, concurrency, restart recovery, resource sufficiency, security or public API publication approval.

Factomaton is engineering author, evaluation decision actor and recorder. Factfinder is the prior exact integration reviewer; shared Adrian ownership, prior source/design exposure and authored fixtures are disclosed. This is no independent-owner, blinded, held-out or non-author curation result. Q7's completed Task and prior acceptance remain immutable; this independent owner-authorized follow-on evaluation is not its extension, reopening or submission.

Next: define one separately pinned real-model candidate diagnostic and resource/consent scope before any production replacement. Historical runtime/growth acceptance and the W020 provenance hold remain separate.

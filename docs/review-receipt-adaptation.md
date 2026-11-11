# Exact review declaration adapter

`python -B scripts/review_receipt_adapter.py --receipt RECEIPT --root REPOSITORY`
validates the `exact-code-review-declarations-v1` profile and calls the unchanged
S2 committed Git source checker with a separate ephemeral projection. It reads
files and Git objects; it writes no receipt, journal or runtime state.

Supported input has integer `schema_version: 1`, `kind` or `artifact_kind` equal
to `exact_code_review` (both may appear only with that same value), a declared
`decision` of `accept`, `revise` or `unresolved`, a full lowercase Git commit ID,
and 1–256 `source_raw_bindings`. Paths must be canonical public relative POSIX
paths, at most 512 characters, without backslashes/control characters; digests
are lowercase SHA-256. The shared strict parser rejects duplicate keys,
fractional/nonfinite numbers, integers outside the portable range and input
larger than 1 MiB. Canonical projection size is also bounded before Git reads.

Original bytes remain untouched. Top-level receipt hashes identify those bytes
and their factori-sorted-json-v1 canonical form. `normalized_projection_sha256`
identifies a separate canonical projection containing only schema/type,
decision, commit and file bindings. The nested `projection_source_binding`
hashes refer to that projection, never the original receipt. Unknown original
fields remain covered by the original digest but are not validated or carried
into the projection. This is a declaration profile, not full artifact-schema,
role, prose, reviewer-identity or authority validation.

All three declared verdicts permit byte comparison. A matching `revise` remains
a declared `revise`; no verdict permits a runtime approval transition. A match
only says the declared file hashes correspond to historical committed bytes.
Target-tree drift stays explicit in S2's nested result. Missing/mismatched files
are reported separately; coverage completeness remains unverified. No minimum
required file set or adequacy/independence judgment is inferred.

Imported authentication and implementation/runtime review stay unverified or
pending. Full-content decisions, corrections, fresh trusted observations,
reviewer ownership/authorization, source coverage completeness and deployed
build identity need separate verification. No S1/S2/S3/S4/S5/S6 source/schema or
frozen review changes, automatic gate, live database, API or deployment change
is part of this increment. Passing synthetic consistency tests is not factual
approval or authenticated provenance. A new exact technical review is required
before integration.

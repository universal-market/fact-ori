# Portable sidecar digests

W012 uses `factori-sorted-json-v1` for a detached canonical sidecar digest.
Run either entry point against a JSON file.

```sh
python -B scripts/sidecar_digest.py path/to/sidecar.json
node scripts/sidecar-digest.mjs path/to/sidecar.json
```

Each command returns canonical JSON text, its UTF-8 byte count and SHA256,
plus the original file's byte count and SHA256. The detached digest includes
every artifact field, including referenced hashes, supersedes references and
any field named `sha256` or `digest`. Keep the artifact's own canonical digest
outside that artifact.

Canonicalization sorts object keys by Unicode code point, uses compact JSON
commas and colons, emits ASCII escapes for non-ASCII characters and DEL, and
encodes UTF-8 with zero BOM or trailing-newline bytes. Unicode strings retain
their original normalization. Supplementary characters use escaped UTF-16
surrogate pairs. Integer-looking object keys retain Unicode sort order.
Arrays retain element order. A negative-zero integer token canonicalizes to
`0`. File formatting and its trailing newline contribute to the raw hash.

This first implementation supports decoded JSON objects, arrays, strings,
booleans, null and integers between `-9007199254740991` and
`9007199254740991`, inclusive. The portable integer range is an implementation
choice for JavaScript's exact numeric representation. Both file entry points
require integer number tokens and reject decimal/exponent forms, including
forms that would round to an integer. UTF-8 input is decoded strictly.
Invalid or unsupported input exits with status 2. Standard JSON decoding
keeps the last value when an input object repeats a key.

The Python `canonical_bytes` and JavaScript `canonicalJson` functions accept
decoded values in this domain. JavaScript callers supply safe integer
numbers and ordinary string-keyed data objects. Fixed vectors exercise both
file entry points, Unicode ordering, normalization distinctions, escaped
controls, surrogate strings, integer bounds and detached field inclusion.

The accepted proposal is W012 v2, SHA256
`568dbf92a5c4741f6c30b9350f3a6e558bab141fe51ccc1463a913eafe20a560`,
with examples v3 raw SHA256
`c5a14a8f4c8801b44b85d7299fefe3dd7328e2933ad4977b8c394e29b93eb1e1`.
Its design acceptance is Tilori post `194b9ff0-4656-4458-a9ca-36a65f7c768b`
revision 1. This digest-tool increment receives a separate technical review.
Ownership observations, review/record bindings and coverage mappings belong
to the subsequent inspection adapter.

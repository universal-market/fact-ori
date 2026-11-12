# Staged semantic snapshot boundary v1

`service/snapshot-boundary.mjs` exports `assertPublicSnapshot`. This standalone
module is not imported by the engine/server and changes no deployed API behavior.
It addresses R1/R4 from the immutable W015 runtime compatibility evaluation:
unsupported offline artifacts must not silently become an empty approved index.

The validator permits only the complete schema1 static public snapshot envelope.
It checks required arrays, consumed record strings, positive safe-integer versions,
64-character lowercase hash shapes, approved package state/identity/version/answer,
unique record and literal-query identities, and exact mapping target/version/hash
consistency. Clarification mappings cannot carry claim targets. Explicit withheld
metadata stays separate from approved rows. Empty approved snapshots are valid.
Unknown top-level fields require explicit format evolution. Literal queries are
neither trimmed nor case-normalized; distinct case/spacing keys remain distinct.

These checks establish structure and internal consistency only. They do not
recompute canonical record/snapshot hashes, authenticate signatures or curation,
prove source truth/currency/completeness, validate the full audit schema, or
prevent a coherently invented approved snapshot. Hash-shaped strings can pass
without matching content. Existing runtime/backend freshness gates remain needed.
The fixed error code INVALID_PUBLIC_SNAPSHOT and message never echo input values.
The module has no imports, I/O, mutation, model/backend calls or vector indexing.

Six tests use the actual eight-record export and actual withheld seed/export,
forged-kind/version attempts, envelope/type/pin/state/duplicate mutations,
empty and withheld metadata, literal identity and coherent-invention limits.
Run `node service/snapshot-boundary.test.mjs` or `npm run test:semantic`.

Factomaton is author, engineering decision actor and recorder, and prior
implementation/design/source-review author. Intended reviewer Factfinder shares
Adrian ownership and prior fixture/source/design exposure. This is not blinded,
held-out, independent-owner or non-author curation. Prior Q1–Q5 receipts remain
immutable; this is a new exact technical review scope, not a Q5 Task extension.

Next: fresh exact module review in a zero-cost Market contract. Only after separate
recipient assessment should a bounded integration wire it before indexing and
measure startup/restart/error behavior. The production engine, fingerprint,
server startup and all active inputs remain unchanged now. Explicit offline
pending literal diagnostics, approved predicate projection selection, Convex
storage/inspection and later curation/growth/runtime/API consent remain separate.

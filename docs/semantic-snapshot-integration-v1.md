# Semantic snapshot boundary integration v1

This separate implementation follows Q6's exact standalone module acceptance.
The accepted `snapshot-boundary.mjs` bytes remain unchanged. Q6's original source,
review, recipient assessment and all earlier receipts remain immutable history;
this integration needs a fresh exact review before deployment.

The server parses and validates its snapshot before opening or migrating SQLite,
resetting interrupted requests, listening or identifying models. File/JSON-load
errors use a fixed INVALID_PUBLIC_SNAPSHOT diagnostic without parser excerpts or
input paths. The engine validates at construction before its first SQL operation,
and validates again at initialization before embedding or vector writes. Rejected
reinitialization clears in-memory candidates; existing cache rows are retained
but are not admitted as candidates. Valid empty snapshots remain representable.

The engine fingerprint now includes the accepted guard's bytes, so changing the
guard changes the revision used by existing restart/result invalidation rules.
The existing Docker recipe already copies the full service directory; no image
build, service restart, migration or deployment was performed this cycle.

Five integration test groups cover invalid construction before DB/model calls,
whole-snapshot rejection before the first vector, rejected reinitialization,
valid eight-record cold/warm cache behavior, empty index, invalid server startup
and repeated restart without state creation/migration/result mutation/listening,
non-echoing malformed JSON errors, and guard-byte fingerprint changes. The two
old engine fixture builders now restrict mappings to the selected record subset;
all 25 existing engine assertions retain their prior checks. The existing HTTP
suite continues to exercise valid startup/restart and engine-revision rejection.
Run `npm run test:semantic` (50 tests including these five new groups).

This changes runtime source, not the active library or deployed service. It is a
structural format boundary, not snapshot content-hash authentication, factual or
curation approval, currency/completeness/full-audit/security/resource proof.
Coherently invented approved envelopes can still pass as documented in Q6.
Finite answer kinds, pending literal diagnostics, approved predicate selection,
Convex storage, non-author curation and growth/runtime/API consent remain separate.

Factomaton is engineering author, decision actor and recorder, also prior
implementation/design/source reviewer. Intended reviewer Factfinder shares Adrian
ownership and prior candidate/source/design/code exposure/authored fixtures; no
independent-owner, blinded, held-out or non-author curation claim is made.

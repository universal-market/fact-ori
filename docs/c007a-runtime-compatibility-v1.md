# C007a runtime compatibility evaluation v1

This owner-authorized engineering evaluation follows Q5's exact offline
acceptance. It does not extend or reopen the completed Market review Task.
Author, engineering decision actor and recorder: Factomaton, also implementation/
design/source reviewer. Candidate/prior reviewer Factfinder shares Adrian owner,
prior exposure and authored fixtures. No independent-owner, blinded, held-out or
non-author curation claim.

Run `npx vitest run tests/c007a-runtime-evaluation.test.ts` and
`node data/W015-runtime-evaluation-v1/semantic-probes.mjs` from the repository
root. Four Convex tests and three semantic cases pass. Semantic result bytes
repeat exactly. Input hashes, normalized result receipts and limits are in
`data/W015-runtime-evaluation-v1/evaluation.json`. Convex uses actual current
schema/functions in an isolated `convex-test` database. Semantic tests use the
actual engine, memory SQLite and deterministic model/backend stubs. No active
database, network/model service, source capture or deployment is used.

The offline seed cannot be directly imported: the actual Convex boundary rejects
it with no database rows written, and semantic initialization raises a TypeError
because the seed has no `records`. A deliberately forced legacy pending wrapper
does import in memory, but all three query aliases and record inspection withhold.
The current alias normalization collapses case/spacing and cannot encode Q4's
literal-codepoint matching policy; pending inspection also hides its audit.

A deliberately **bypassed synthetic approval**, using the full original package
answer, makes current Convex aliases return that same compound answer for P1,
P2 and P3 and their uppercase variants. The semantic engine likewise returns
the compound answer for each predicate with approving model/backend stubs.
These are tests of a trusted-import interface gap, not real curation decisions,
an externally exploitable path, production leakage or measured model behavior.
The current package-answer interface cannot select the exact reviewed predicate
answer/source projection.

The offline export diagnostic has empty records/mappings. The semantic engine
accepts that shape and initializes zero records, then returns `not_in_library`
for all three queries without recognizing pending routes. No answer leaks, but
an accidental unsupported-format wiring would silently lose pending coverage.
This distinguishes a format guard from the later substantive routing changes.

The selected next increment is a strict semantic snapshot-format boundary,
followed by an explicitly separate offline pending-diagnostic path before vector
indexing. Reject unsupported kinds instead of silently indexing them. Keep
pending literal keys and catalog/record/review pins separate from approved model
records, always withhold and preserve original audit references. Freeze and
review exact implementation inputs before any active wiring. Convex predicate
storage/inspection and approved predicate answer selection are later work.

Only evaluation files were added; production source and four active inputs are
unchanged. No full regression rerun is claimed. Accepted source limitations,
unverified caller context, W020 provenance requirements, non-author curation,
growth/snapshot/runtime evaluation and API consent remain separate.

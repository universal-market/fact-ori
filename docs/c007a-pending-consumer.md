# Offline schema-2 query and export propagation v1

The explicit Python entry points `export_api_seed.build_pending_snapshot`,
`ask.lookup_pending` and `export_public_snapshot.export_pending` carry the
reviewed C007a literal routes through a separate withheld consumer format.
Default functions and CLIs continue to use the original eight-record library.
No active input or public snapshot is changed, and Convex/runtime integration
remains future work.

All three functions require the exact catalog/proposal/record/review bytes,
attachment manifest, caller-supplied current post context and offline selection
state. The seed builder reuses the exact routing/attachment boundary. After a
JSON roundtrip, query/export rederive the expected entire seed and compare strict
canonical JSON, rather than trust stored approval fields or a caller's digest.
Type substitutions, extra fields, duplicate queries, changed bindings/sources,
answer injection, stale selection reuse and newly adverse context reject. This
does not authenticate the context: coherent invented context still passes. W020
authenticity/freshness/completeness requirements are unchanged.

`offline_withheld_predicate_seed` schema 2 uses `withheld_claim` and
`literal_routes`; it has no `versions`, `claims`, `aliases` or `importId` and
is not an active Convex seed. The legacy schema-1 question reader rejects it.
Exact literal queries return `withheld` and a metadata diagnostic; altered or
unknown literals return `not_in_library`, no diagnostic, and no factual false
verdict. All answers remain null, API activation false and curation event null.
All four pending/reopened/retired/unselected display states follow that rule.
There is no approval state or answer-enabling switch.

Proposed answer strings, original full record/review bodies and selected source
copies are omitted from consumer seed/query/export output. Exact audit input
hashes and bindings point back to the immutable full artifacts; source review
coverage, dependence and revision history remain there without being rewritten.
Literal route diagnostics preserve predicate/source IDs and scope/clarification
constraints. Those constraints and query strings can contain factual text: this
is not a general claim-text redactor, public schema approval or privacy boundary.
The public-export diagnostic always has empty `records`/`exact_mappings`, one
withheld row and `not_for_publication=true`; the default public exporter does not
call this path.

Run `python -B -m unittest discover -s scripts -p 'test_c007a_consumer.py'`.
The frozen `scripts/fixtures/c007a-v3/pending-consumer-results-v1.json` contains
one seed, fifteen lookup results and one export diagnostic for the explicitly
unverified fixture context. Its regression checks exact serialized roundtrip,
all four states, literal variants, nested tampering and mutation isolation, and
the original default view/seed/public snapshot outputs.

Author/engineering decision actor/recorder: Factomaton, also implementation/
design/source-review author. Intended exact integration reviewer Factfinder
authored the candidate/prior design/code/source reviews. Shared Adrian owner,
prior exposure and authored frozen fixtures; not blinded/independent-owner/
held-out/non-author curation. Q4 acceptance applies to the exact prior source
commit. These additive query/export entry points change those files' hashes and
need fresh exact integration review. Frozen historical files remain intact in
their original commits. Later active propagation, non-author curation, growth/
snapshot/runtime evaluation and API publication consent remain separate gates.

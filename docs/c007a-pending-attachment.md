# Offline C007a pending attachment

`scripts/c007a_pending.py` joins the exact reviewed input boundary from
`c007a_preview.evaluate` to a record-only `library_view.derive_view`. It consumes
one versioned attachment manifest plus the original pinned record/review/design
bytes. The manifest at `scripts/fixtures/c007a-v3/attachment-manifest-v1.json`
binds the full candidate input and source-review pointer. Canonical JSON equality
rejects missing/extra fields and bool/int/float substitutions; no arbitrary
review schema or conflicting attachment is selected by heuristics.

The full original detached source review remains in `detached_source_reviews`,
with raw/canonical hashes, unchanged kind and original actor/reviewer/owner/input
fields. Legacy `reviews` stays empty. Nothing is coerced into a legacy review,
and the validator and frozen artifacts are unchanged. Current review state is
accepted **on these exact offline inputs**, while the original no-review note is
separately labeled creation-time history and every other limitation is retained.

The version-2 wrapper is an offline pending integration view, not an active
manifest format. `selection_state` may be pending/reopened/retired/unselected
only; it is a display choice, not a curation receipt. No curation event is
generated. Every output keeps answer null, answer_kind withheld, API false,
curation not_evaluated and routing implementation review pending. Tests call the
existing query lookup with these views and demonstrate withholding for all four
states and all three predicate queries. No predicate answer projection or
literal-query router is enabled by this component.

Caller-supplied post context remains unverified. A coherent invented context can
pass; no authentication, freshness, completeness or remote correction visibility
is established. Unknown/unresolved/withdrawn or changed context rejects. This
does not weaken W020's separate provenance requirements. Active loaders, public
exporters and the API do not import the module or load its snapshot fixture.

The pending-view JSON fixture is generated from explicit invented post context
matching the pinned IDs/revisions. It is reproducible offline evidence, not a
claim that those post observations were captured or authenticated by this code.
The full frozen review in the fixture is audit data, not an enabled answer.

Run `python -B -m unittest discover -s scripts -p 'test_c007a_pending.py'`.
Fresh exact implementation review and recipient assessment remain necessary.
Active integration, predicate-projection/routing review, non-author curation,
growth/snapshot evaluation and publication consent are separate later gates.

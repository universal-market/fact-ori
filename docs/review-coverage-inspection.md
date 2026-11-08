# Inspect legacy review coverage

Inspect the currently selected record and its manifest source reviews.

```sh
python -B scripts/inspect_review_coverage.py C009
python -B scripts/inspect_review_coverage.py C005 --root /path/to/fact-ori
```

The command uses the existing validated library and API seed. Its JSON contains
the complete frozen record, current evidence package and original source review
objects, alongside an additive legacy projection. It supports the selected
version of each library claim. Unknown claims and inconsistent library inputs
exit with status 1.

`decision` exposes the declared decision actor, reviewer and recorded-by agent.
Older receipts derive the actor from their reviewer field and label that basis.
Unknown recorder identities stay null. C009 illustrates Factomaton as factual
decision actor and Factfinder as receipt assembler. C005 retains its declared
shared-owner relationship and an unknown verified relationship.

Original `reviewed_at` is preserved as `legacy_reviewed_at`. Explicit decision,
recording and post-publication fields retain their own meanings. Unsupported
original times stay null. `assembly.assembled_at` identifies this inspection's
generation time. The raw review retains all original time-basis declarations.

`binding` reports record consistency, receipt IDs/revisions, declared body hash
and its comparison with embedded review text. Missing fields, body mismatches
and actor disagreement appear in unresolved reasons. Each raw review also gets
a detached canonical object digest through the merged W012 digest tool.
`live_receipt_status` remains `not_checked`. Current server revisions,
withdrawals and authenticated historical ownership need a separate verifier.
Existing ownership observation declarations remain available in the raw review.

`target_inventory` preserves each evidence entry at its exact JSON pointer and
lists claim, scope, answer and other available statement fields. Extent starts
as `unknown`. Source checks and checked/unchecked prose remain verbatim under
`unmapped_legacy`, even when source URLs match the evidence. Explicit source
IDs, retrieval times, carried-forward checks, capture data, source dependence
and alternative-source details remain in the raw review. A reviewed mapping
is required to turn any of these declarations into normalized target coverage.

The projection carries an exact reference to accepted W012 proposal v2 and
examples v3. This increment covers legacy inspection of manifest source reviews.
Supplemental receipt discovery, sidecar mapping, authenticated observation
verification and integration into the hosted API are subsequent increments.
The evidence package retains its curation state, answer kind, scope and factual
verdict. C009's selected package continues to express a reviewed abstention.

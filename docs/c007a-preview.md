# C007a/v3 offline preview

`scripts/c007a_preview.py` implements one deliberately withheld-only step of the
accepted design at `cdfa2208e82e2e288b2784adbf7309366995d2e8`. It is not imported
by the active consumer, exporter, API or deployment. It has no activation flag,
network reader, file writer or answer-enabling path.

`evaluate(query, proposal_raw, record_raw, review_raw, current_posts=...)` requires
the three exact pinned byte strings. It rejects changed versions, digests,
anchor bindings, substituted historical reviews and changed review/design bytes.
It projects the frozen no-review note as creation-time history, separately
attaches the later exact source decision and retains every other limitation,
source-review coverage, source dependence and disclosed roles.

The query must equal one of the 15 reviewed strings byte-for-character. The
returned `proposed_after_gates` describes conditional future route coverage, not
an enabled answer or a factual verdict about the question. Other strings return
`unmapped`. All successful outputs have `answer: null`, pending curation and
implementation review, and `api_activation: false`.

The caller must supply exactly the three post IDs in `POSTS`, with integer
revision 1, null status, exact author/owner IDs and explicit `correction_state:
"clear"`. Missing, extra, drifted, unknown, unresolved or withdrawn inputs fail
with a constant diagnostic. This is a caller declaration: it does not establish
authentication, freshness, visibility, completeness or absence of hidden/later
corrections. Coherent invented context can pass. Output explicitly says
`unverified_caller_supplied_context`. This component cannot certify the current
remote state, resolve corrections or authorize an answer.

Test fixtures in `scripts/fixtures/c007a-v3` are byte-identical copies of the
original record at `2e800bda7173071c79843894a5de064cf97ec356` and detached source
review at `0489f67574ece2b5cec8b318366b9b8e7b9c3234`. They are immutable test
inputs, not new factual artifacts or reviews. Their raw hashes are pinned in
the component. The proposal remains in its original data path. Tests mutate
copies in memory and need neither historical Git objects nor network access.

Run `python -B -m unittest discover -s scripts -p 'test_c007a_preview.py'`.
These tests exercise finite preview/rejection behavior, not general NLU,
empirical factual accuracy or production routing. Fresh exact implementation
review, active-consumer integration, non-author curation, growth/snapshot checks
and publication consent remain separate requirements.

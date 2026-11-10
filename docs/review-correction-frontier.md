# Bounded correction-frontier observations

`scripts/acquire_review_frontier.mjs` exports
`acquireReviewFrontier(callRead, {capture_request, max_pages})`. It composes the
existing four-read S3 acquisition without changing that reviewed module or its
capture schema. The host supplies the same ordinary-content adapter. There is
no credential access, subscription, listener, periodic retry or write.

After matching identity and exact revision observations, it reads up to 1–10
pages of `search_posts` with the exact decision root, unlimited subtree depth,
creation ordering and 20 items per page. Empty pages with cursors continue.
Only a null cursor establishes observed pagination completion. Budget exhaustion,
repeated cursors, duplicate IDs, malformed responses and access failures remain
pending. The returned cursor and original accepted-size JSON observations are
retained. Resuming requires a fresh acquisition with a larger bounded budget;
appending old pages could omit changes and is not implemented.

Every discovered reply is retained as an exact ID/revision/author/owner reference
and keeps the result pending for full-content review. Summaries cannot establish
that a reply is a correction, withdrawal, replacement or harmless acknowledgment.
The module interprets no fetched prose and does not restrict search to the
original author. This deliberately also withholds on third-party objections and
benign replies. A separate actor must fetch complete current reply bodies and
their corrections before a later, separately versioned decision.

A final decision reread detects observed revision, text, author, owner, editor
or status changes during scanning. Missing, changed or inconsistent total reply
counts also keep pending, including an empty search that omits counted replies.
Non-null status requires explicit review.
Unreadable results never establish deletion or its cause. A restored-access
attempt needs a new capture ID and a complete new frontier acquisition.

`frontierFreshness(envelope, nowMs, maxAgeMs)` reports only whether the start,
finish and retained observation timestamps fit the caller's explicit age bound.
It rejects missing, invalid, future, inverted and stale timestamps. It grants no
authority and selects no production freshness SLA. The caller must separately
check diagnostics, pagination completeness, exact inputs and reply dispositions.

`empty_frontier_observed` means an empty visible subtree was observed in this
sequence. It cannot prove absence of hidden, unlinked, concurrently inserted or
later corrections. Neither rereads nor pagination provide an atomic snapshot.
The host adapter and imported envelope remain forgeable. Receipt authentication
is always `unverified_import` and implementation review is always `pending`.
This separate envelope is not directly accepted by the S1 capture journal.
Strict JSON duplicate-key validation, durable frontier storage, semantic reply
dispositions, source/runtime integration and exposure-path freshness enforcement
remain separate work. No public API or deployment behavior changes here.

Run `node scripts/test_acquire_review_frontier.mjs` and the existing S3 tests.
Factomaton authored this increment; exact different-agent review is pending.

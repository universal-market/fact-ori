# One-shot review capture acquisition

`scripts/acquire_review_capture.mjs` exports `acquireReviewCapture(callRead,
request)` for an operator host with an existing authenticated Tilori connection.
The host supplies `callRead(name, arguments)` returning the connector's original
JSON text as `result_json` and its error flag as `is_error`. The module handles
no credentials and starts no listener, subscription or polling loop.

The request supplies canonical capture, recorder, reviewer and decision-post
UUIDs, a positive exact decision revision, full reviewed Git commit and expected
raw receipt SHA-256. Four fixed sequential reads collect current recorder and
reviewer identity, the current decision post and its exact revision. Identity
comparisons use UUIDs and observed owner IDs. Handles remain display metadata.
Identity/author failures stop dependent reads. Changed revisions, unexpected
editors or unequal current/pinned text produce pending diagnostics. Read errors
preserve their returned payload without interpreting why access failed.

Responses are capped at 262,144 UTF-16 code units. Invalid/oversized adapter
responses and transport exceptions receive bounded generic error observations;
transport exception text may contain private details and is discarded. Original
JSON text is preserved for accepted-size responses, including explicit errors.
Malformed JSON is pending and requires investigation before journal import.

The returned `capture` can be passed through the existing strict Python receipt
journal entrypoint with the original receipt bytes. That entrypoint rechecks
strict JSON, digest and canonical-size limits before storage. Keep the collector's
diagnostics alongside the capture as a separate observation. Use a fresh capture
UUID for each acquisition attempt, including a restored-access reread.

The host adapter is a trust boundary. A test adapter or imported JSON can forge
the same output, and this module does not attest the host, sign observations or
authenticate receipt decisions. `identity_revision_observed` describes matching
observations in one read sequence. `receipt_authentication` remains
`unverified_import` and implementation review remains `pending`. Concurrent
edits can occur between reads. Full schema/duplicate-key validation occurs at
journal import, and complete correction/visibility/lifecycle/frontier/source
coverage and runtime verification require subsequent implementation and review.

Run the adapter regressions with `node scripts/test_acquire_review_capture.mjs`.

# API development contract

The local Convex HTTP endpoint defaults to `http://127.0.0.1:3211`.
The generated `CONVEX_SITE_URL` in the ignored local environment file gives
the configured endpoint. `GET /health` reports import and implementation
review status.

## Check text

```http
POST /v1/check
Content-Type: application/json
Idempotency-Key: optional-client-request-key

{"text":"How many millilitres are in one litre?","public_review":false}
```

Inputs contain 1–4000 UTF-16 code units (JavaScript string length; an astral
character uses two units). The initial implementation checks a single
submitted question or canonical claim. Case, whitespace and trailing question
marks are normalized. Reviewed exact aliases and exact frozen claim wording
can return `answer` or `abstain` with a scoped evidence package and pinned
inspection reference. Ambiguous mappings return `needs_clarification`.
Approval or mapping drift returns `withheld`.

Exact canonical wording selects the currently approved version; it is not a
client-supplied version pin. The response identifies that version and hash for
pinned inspection. Import rejects aliases that collide with another incoming
claim's normalized canonical wording, and clarification aliases that shadow any
incoming canonical claim. A same-claim alias remains valid. Canonical wording
shared by multiple claims without an alias returns clarification. These checks
use the existing normalization; Unicode folding is not enabled.
Canonical lookup selects the active import in its database index before limiting
matches for ambiguity detection. Retained historical rows do not consume that limit.

Other text returns `not_in_library`, `answer: null`, full-text candidates and
their scope. Candidates carry `scope_match_established: false`.
The initial retrieval method is `full_text`. Semantic matching and paragraph
claim decomposition are follow-up work.

Setting `public_review` to true persists an unresolved submission as public
research work. Normalized duplicate submissions share one job. Valid request
keys apply only to opted-in unresolved queue submissions. Other response paths
ignore them, including opt-out, answers, clarification and withholding. Those
paths reserve no key and persist no submission. Within the public queue,
reusing a key for different normalized text returns HTTP 409. Queued requests
return HTTP 202 and a stable job ID. The queue has a 500-unstarted-job cap.

For a read-only public launch, the operator sets deployment environment variable
`FACT_ORI_PUBLIC_READ_ONLY=true`. Then any valid `public_review: true` request
returns HTTP 403 before dispatching the check mutation, storing no job or
idempotency key. Omitted/false consent still permits ordinary evidence checks.
Unset or exactly `false` retains local intake behavior; other configured values
(including typos/empty strings) fail closed into read-only mode. This switch is not
a read-traffic quota or rate limiter.

Research jobs expose Tilori progress values `not_started`, `in_progress`,
`blocked`, `done` and `canceled`. Evidence verdict and work progress are
separate. `GET /v1/jobs/{id}` returns job state and the linked Tilori post ID.
Progress includes its source, last observed post revision/time and recorder.

## Inspect exact evidence

```http
GET /v1/records/C005?version=1&sha256=b504d25ad24114e3b9bf95886ba0557eaa6920bc3650a37c27cb848f893fbb28
```

All three pins are required. Inspection returns the current approved
projection, exact frozen source record and full structured source reviews.
This retains derived inference, excluded scopes, ownership, checked sources,
review decisions and curation attribution. State/version/hash drift withholds
the package with HTTP 409. Source freshness reflects the stored retrieval
dates and `live_source_refresh: false`.

## Operator bridge

`npm run outbox` lists up to ten queued and ten expired leased requests.
Operator functions are internal Convex functions accessed through the
authenticated local CLI. A worker claims a specific job with
`checks:claimJob`, a unique worker identifier and a five-minute lease.
Another active worker receives null. Expired unlinked leases become available
again through the outbox.

The librarian searches current Tilori content for existing matching work.
An existing investigation can be linked through `checks:linkJob`. For a new
post, use the returned stable `tilori_idempotency_key` in Tilori's ordinary
posting tool, then link the resulting post. Retrying the same posting key
recovers the original result. A worker checks its lease before linking.

During a work session, internal `checks:listForReconciliation` pages linked
jobs by status, with `paginationOpts` containing a cursor and a 1–100 item
page size. Linked jobs remain available there after handoff, including when
their remote status is queued again. `listQueued` lists unlinked work only.
The operator reads the linked post through ordinary
Tilori content tools and reads the current job. When the post carries an
explicit task status, call internal `checks:reconcileJob` with the exact
job/post IDs, post revision/status, observation timestamp, recorder identity
and the job's current `updated_at` as `expectedUpdatedAt`. The mutation checks
the binding, monotonic observation/revision and optimistic update token.
Conflicting status at the same post revision is rejected. Exact retries are
idempotent. A later post revision can reopen completed work.

The operation can record `blocked`, `done` or `canceled` after linking,
including an existing completed investigation. Until an explicit post status
is observed, progress is labeled `operator_handoff`. After reconciliation it
is labeled `tilori_post`. A completed job describes research progress and
carries no factual verdict or publication approval.

This bridge is operator-driven during work sessions. The local backend stores
the queue between sessions. Launcher and subscription delivery belong to the
existing Tilori connector.

## Current implementation boundary

This is a local development API with `implementation_review: pending`.
Every JSON response emitted by the registered HTTP handlers also includes:

```json
{
  "implementation_review": "pending",
  "implementation_provenance": {
    "schema_version": 1,
    "binding_state": "unconfigured",
    "source": null,
    "build": null,
    "review_receipts": [],
    "historical_receipts_loaded": false,
    "reason": "Runtime source/build identity and authenticated review receipts are not configured."
  }
}
```

This includes health, evidence answers/abstentions, clarification, withholding,
candidates, records, jobs and handled validation/backend errors. The envelope
comes from server code, overriding any result-level review labels; public
request fields cannot install it. `review_receipts: []` means no historical
receipts are loaded into this runtime, not that the project has never been
reviewed. It does not change the evidence verdict, publication state, HTTP status
or queue consent. OPTIONS remains bodyless (204); unmatched routes and platform
errors outside these handlers are outside this JSON contract.

Only `unconfigured` is implemented. Source/build identity verification,
authenticated immutable receipt recording, stale/withdrawn/missing receipt
evaluation and scoped acceptance require a later reviewed increment. No receipt
installation endpoint or deployment attestation is supplied by this envelope.

Public writes are limited to opted-in research requests. Record import,
curation selection and worker mutations are internal. Production launch
requires a hosted deployment, client quotas/rate limits, reviewed request
handling and an operational bridge. Local Convex deployment state and
environment files remain outside Git.

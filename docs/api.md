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

Inputs contain 1–4000 characters. The initial implementation checks a single
submitted question or canonical claim. Case, whitespace and trailing question
marks are normalized. Reviewed exact aliases and exact frozen claim wording
can return `answer` or `abstain` with a scoped evidence package and pinned
inspection reference. Ambiguous mappings return `needs_clarification`.
Approval or mapping drift returns `withheld`.

Other text returns `not_in_library`, `answer: null`, full-text candidates and
their scope. Candidates carry `scope_match_established: false`.
The initial retrieval method is `full_text`. Semantic matching and paragraph
claim decomposition are follow-up work.

Setting `public_review` to true persists an unresolved submission as public
research work. Normalized duplicate submissions share one job. Reusing a
request key for different normalized text returns HTTP 409. Queued requests
return HTTP 202 and a stable job ID. The queue has a 500-unstarted-job cap.

Research jobs expose Tilori progress values `not_started`, `in_progress`,
`blocked`, `done` and `canceled`. Evidence verdict and work progress are
separate. `GET /v1/jobs/{id}` returns job state and the linked Tilori post ID.

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

This bridge is operator-driven during work sessions. The local backend stores
the queue between sessions. Launcher and subscription delivery belong to the
existing Tilori connector.

## Current implementation boundary

This is a local development API with `implementation_review: pending`.
Public writes are limited to opted-in research requests. Record import,
curation selection and worker mutations are internal. Production launch
requires a hosted deployment, client quotas/rate limits, reviewed request
handling and an operational bridge. Local Convex deployment state and
environment files remain outside Git.

# Semantic evidence API

`GET /openapi.json` exposes the machine-readable contract.

`POST /v1/check` accepts questions, assertions and paragraphs up to4,000
characters. Curated aliases have a direct evidence response. Other wording
uses local dense-vector retrieval followed by a scope assessment against each
retrieved reviewed answer, its conditions, limitations and source excerpts.

```sh
curl https://YOUR-API/v1/check -H 'Content-Type: application/json' \
  -d '{"text":"How many ml make up a liter?"}'
curl https://YOUR-API/v1/check -H 'Content-Type: application/json' \
  -d '{"text":"Canberra is Australia’s capital. A litre contains 500 millilitres.","async":true}'
```

Sentence segmentation and extracted clauses retain literal source quotes; the
service never accepts a rewritten claim. Code verifies full-word source spans
and coverage of every original content token (only and/but separators may be
omitted). The model audits atomicity on content-obscured text, independently for
each item, so factual beliefs cannot correct the submitted assertions during
parsing. Combined items are split into verbatim quotes and checked again.
Shared input context is retained for references/conditions and is explicitly
unverified, not factual evidence. Structural uncertainty fails explicitly;
atomicity and query relationships remain `model_assessed` rather than human-reviewed.

Each result contains the source quote and character offsets, extracted claim,
status, evidence verdict, answer, candidate records and model assessment.
Compound inputs return a `results` array. Statuses include `answer`,
`contradicted`, `abstain`, `needs_clarification`, `not_in_library` and
`not_checkable`. Model-derived matches carry
`query_relationship_review: model_assessed` and exact model revisions.
Reviewed evidence packages retain their factual reviews and original scope.
Abstentions retain insufficient evidence and publication pins are revalidated.

Analysis taking longer than20seconds returns202 with an ID and `poll_url`.
`GET /v1/checks/{id}` returns progress and the completed result. SQLite analysis
state survives restart. Completed/failed analyses expire24hours after submission,
under unguessable public IDs; pending work remains until processed. State includes
submitted text and results. Library revision changes
invalidate completed and partial responses with409. Submit a new analysis to use new data.
The analysis queue permits100 pending requests. At most12 atomic claims are
supported per request and excessive extraction fails explicitly.

`public_review: true` submits each `not_in_library` claim as a deduplicated durable
research job, retaining unverified input context for shared conditions and
references. If the target-plus-context would exceed4,000characters, the whole
original input becomes one context-preserving job instead of being truncated.
Its text becomes public when the librarian posts or links the
investigation on Tilori. `GET /v1/jobs/{id}` exposes research progress and the
linked post ID. Research completion and analysis completion are separate.
`Idempotency-Key` binds the analysis text and public-review choice, with409 on
conflicting reuse. Research intake retains its500-unstarted-job limit. A queue/backend failure retains
the analysis with `research_submission: unavailable` and no fabricated job.

Operators use `bash scripts/self-hosted.sh outbox` and the allowlisted
`operator` command for the isolated production instance. Librarian work sessions
claim pending jobs, check for existing Tilori investigations, post through normal
authenticated tools, link exact IDs and reconcile observed status revisions.
Container-only deployment authority stays in the existing ephemeral pipeline.

Local `nomic-embed-text:v1.5` and `qwen2.5:14b-instruct` run through isolated
Ollama. `service/models.json` pins their exact content revisions. Vector-cache
keys include the embedding revision and indexed content. Startup checks model
identities. Retrieval ranks current approved records by cosine similarity and
only candidates scoring at least0.70 proceed to the relationship classifier. This
conservative threshold is a coverage gate chosen from authored diagnostics for
the pinned embedding model, not a truth probability or general accuracy claim.
It can miss valid paraphrases; low-scoring inputs return missing coverage rather
than inheriting the nearest record. The classifier evaluates at most two
qualifying packages independently using
explicit categories for same-property support/conflict, changed subject/predicate,
changed conditions/dates, insufficient evidence and ambiguity.

Run `npm run test:semantic` for structural/scope regressions and
`node scripts/evaluate-semantic-api.mjs ORIGIN REPORT.json` for real-model
paraphrase, contradiction, ambiguity, scope-change and compound-input cases.
The launch receipt records actual model results and limits. Source freshness,
shared origins, original review receipts and curation history remain inspectable.

An independent conservative guard prevents answers from crossing explicit years
when the reviewed claim has date/event language. Four-digit conversion values
alone do not establish a dated identity. This guard can withhold potentially
related coverage; it does not replace model-assessed scope checks or establish
a different year's outcome. Inference uses one cache slot and a 24 GiB memory cap. The two-slot/multi-user
cache experiment caused an actual inference-server abort and is disabled.

Analysis states bind an `engine_revision` fingerprint of the serving engine,
HTTP service and pinned model configuration. Engine changes invalidate old
terminal analyses and idempotent replays with409; interrupted work recomputes
from its original input without retaining earlier partial judgments. Use a new
request key to submit a fresh analysis. This self-reported fingerprint is not
authenticated runtime/build attestation. Library revisions are checked separately.

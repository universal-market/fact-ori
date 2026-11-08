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

Sentence segmentation preserves original text. A model audits the whole input
for atomicity and fidelity before any sentence can bypass further splitting.
Combined clauses are decomposed and audited again; no conjunction allowlist
establishes completeness. Failed/uncertain audits fail explicitly;
successful extraction is labeled `model_assessed`, not human-verified.

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
research job. Its text becomes public when the librarian posts or links the
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
the relationship classifier evaluates the top two packages independently using
explicit categories for same-property support/conflict, changed subject/predicate,
changed conditions/dates, insufficient evidence and ambiguity.

Run `npm run test:semantic` for structural/scope regressions and
`node scripts/evaluate-semantic-api.mjs ORIGIN REPORT.json` for real-model
paraphrase, contradiction, ambiguity, scope-change and compound-input cases.
The launch receipt records actual model results and limits. Source freshness,
shared origins, original review receipts and curation history remain inspectable.

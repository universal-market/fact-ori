# Public evidence access

The first distribution artifact is [library.json](../public/library.json).
It contains only currently approved, reviewed record versions selected by the
validated library projection. It includes original frozen records, consumer
evidence packages, source-review receipts and reviewed exact mappings. No
unlisted draft, local inbox, research request or operator configuration is read
by the exporter. Reopened/non-approved records lose their public answer and
mapping; the export retains only their ID, state and selected version as a
withholding notice.

This snapshot is not a new factual approval. Use `evidence_package` for current
publication disposition: raw records deliberately retain historical draft
metadata. A `reviewed_abstention` does not affirm its raw claim. Exact aliases
do not authorize answers to semantically nearby questions.

Regenerate after every reviewed record, mapping or curation change:

```sh
python -B scripts/export_public_snapshot.py --output public/library.json
npm run test:python
```

The test suite compares the checked-in artifact to the active library and fails
if it has drifted. The snapshot's `snapshot_sha256` hashes all other top-level
fields using Python sorted-key, compact JSON with `ensure_ascii=True`, encoded
as UTF-8. Frozen record digests separately use `record_digest` from
`scripts/validate_pilot.py`. The formatted file's raw SHA-256 is different.

`curation_as_of` is the latest curation event, not a source-refresh time. Clients
must fetch the latest branch snapshot before use; a commit-pinned copy is useful
for reproducibility but can become stale after corrections. The static download does not imply a running live-query API.

## Local public API pilot

The owner approved self-hosting on this machine instead of creating another
Convex account. This supersedes the earlier cloud-account prerequisite. Convex
stores this deployment in its own Docker volume; the existing anonymous dev DB
and all UM deployments remain separate. See [the self-hosted runbook](self-hosted.md).
The full stack exposes semantic checking and paragraph analysis through an
allowlisted HTTPS gateway. The semantic service sees only public evidence HTTP
endpoints and its own SQLite state; it has no database administration key.
Local inference has no public port. Model content revisions are pinned.

Opted-in research intake is enabled (`public_intake: "enabled"`). Analysis
requests persist submitted text/results under unguessable public IDs, whether or
not research is requested. Terminal requests expire24hours after submission;
pending requests remain until processed. Do not submit private information.
`public_review: true` separately consents to public research; unresolved claim
text can become a Tilori post. Research jobs retain their durable history.
See the [semantic API contract](semantic-api.md) for lifecycle and limits.

Public API access grants neither repository execution nor database administration.
Contributors submit PRs and run tests in secret-free environments. Deploy only
reviewed source from a trusted operator environment. Do not run untrusted PR
code on this machine, mount the owner's home, Docker socket, other-project
volumes or credentials into any Fact-ori container, or perform personal Convex
CLI login here. Container isolation is not protection against someone who has
host shell access or control of the Docker daemon.

Cloud hosting remains an optional later migration. If used, require a dedicated
Fact-ori identity/team with no UM or personal-project membership, provision from
trusted owner context and use deployment-scoped permissions. A standing CI token
needs deployment permission only; seed/import authority belongs in a separate
trusted operation. Never give contributors broad personal tokens or cloud admin
keys. No paid plan or spending commitment is authorized.

Current capability: exact aliases, dense semantic retrieval, model-assisted scope
assessment, paragraph/compound claim decomposition, asynchronous restart-safe
analysis and opted-in research jobs with Tilori handoff. Per-user quotas,
authenticated runtime source/build/review binding, production uptime guarantees
and general accuracy measurement remain future work. Seven reviewed records
provide limited subject coverage; local model routing can err and is disclosed.

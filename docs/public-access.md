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
There is no live-query URL until the pilot is verified and its HTTPS tunnel is started.

Only approved evidence reads are initially public. Research intake is disabled.
`/health` exposes `public_intake: "disabled"` from the same predicate that guards
intake. The read-only probe requires that value before checking the import,
reviewed exact mappings and pinned records; it never attempts a queue write.
Unset or exactly `false` retains opt-in intake for private local development;
all other configured values disable it. The launch sets `true` before code push.

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

Current capability boundary: full-text candidate retrieval and reviewed exact
questions are implemented. Semantic search, paragraph decomposition, hosted
quotas and authenticated runtime source/build/review binding remain unfinished.

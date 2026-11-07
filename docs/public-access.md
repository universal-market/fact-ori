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
for reproducibility but can become stale after corrections. There is no hosted
live-query URL until cloud deployment is completed.

## Hosted Convex API

Use a separate, explicitly selected cloud project/deployment. Keep the existing
anonymous local database for development; do not tunnel its ports to the public
internet. The target is a public `https://<deployment>.convex.site` HTTP API.
All imports, curation, worker and administrative functions stay internal; no
public database console or deploy credential is part of the product.

The local CLI currently reports no signed-in Convex account. It cannot provision
the hosted deployment until the owner connects an account through Convex login.
No deploy key should be pasted into chat, the repository or a Tilori post.
Cloud setup must use a free plan with no paid upgrade or spending commitment.
Verify account limits and plan in the control plane before provisioning.

After account connection, the operator should:

1. Identify the intended team and create/reuse a dedicated `fact-ori` project,
   checking for duplicates before creation. Create an explicitly named cloud
   deployment without changing the local development selection.
2. Set `FACT_ORI_PUBLIC_READ_ONLY=true` on that cloud deployment **before code
   is exposed**. The initial launch permits checks/record reads and rejects
   public research intake with HTTP 403. The flag defaults to the current local
   behavior when unset; deploying without it is not this read-only launch.
3. Deploy the exact reviewed branch/commit to the explicitly selected target.
   Record code commit/tree, target, deployment time, checks and source-manifest
   digest. These are operator records, not authenticated runtime attestation;
   `implementation_review` remains pending.
4. Generate the existing validated import with `scripts/export_api_seed.py` and
   invoke internal `library:importSnapshot` on that same explicit target.
   Do not copy the entire local database: its queue/worker state is not launch
   data. Do not run the current default-target `npm run seed` blindly against
   cloud. Provisioning/deploying does not seed approved evidence automatically.
5. Verify health, exact answer, reviewed abstention, pinned record, scope-mismatch
   candidates, invalid input and disabled public intake. Confirm no job/key was
   persisted. Use a cloud-specific read-only probe; the existing `test:api` is
   intentionally local-only and mutating and must remain so.
   `node scripts/probe-public-api.mjs https://<deployment>.convex.site` is a
   read-only probe against the checked-in snapshot. It never requests public
   intake and checks the exact import ID, mappings, records and a scope mismatch.
   Test disabled-intake rejection separately after verifying the target flag.
6. Publish the verified HTTP base URL and public snapshot URL. Keep active
   deployment updates tied to reviewed source/data changes and monitor the free
   plan's usage. Public write intake requires a separate quota/rate-limit and
   operational review before enabling it. Read-only does not make read traffic
   free or unlimited.

Current capability boundary: full-text candidate retrieval and reviewed exact
questions are implemented. Semantic search, paragraph decomposition, hosted
quotas and authenticated runtime source/build/review binding remain unfinished.

# Market task workflow

Assignments and completion tracking move to Universal Market. Tilori remains
available for discussion, evidence records and product bug reports. Historical
Tilori tasks and review receipts remain intact.

`data/market/project-task-migration-v1.json` contains drafts for the 17 existing
unfinished work items. A draft is not a listing, accepted contract or assigned
Task. Existing ownership and unresolved dependencies must be checked before
publishing each request. Completed work is excluded.

Use only free templates. A fact-finding deliverable must contain a scoped claim,
primary sources and precise locators, retrieval dates, supporting/challenging
evidence, source dependence, uncertainty and an explicit assessment. Lack of
evidence is not a false verdict. Do not require artificial opposing evidence.
Disclose authorship, shared ownership and reused work. Submission, technical
review, factual review and library publication are separate decisions.

For `work-free@1.0.0`, the contract output is a deliverable string limited to
4096 bytes. Use a durable public evidence-artifact URL, its SHA-256 and a concise
summary; the full evidence record may be longer. Submission supplies no implied
recipient acceptance or transaction reputation. Both parties must assent.

The initial listing attempt was rejected. Its exact nonsecret request is in
`data/market/first-listing-request-v1.json`; its receipt records
`REMOTE_RESULT_UNKNOWN_DO_NOT_RETRY`. Subsequent listing readback was empty.
Plugin0.1.45 exposed `INVALID_CONTRACT_INPUTS`: the original bare UUID recipient
and missing performer were invalid. Both inputs must be Party objects:

```json
{
  "recipient": {"principal": "um:agent:YOUR_AGENT_UUID"},
  "performer": {"principal": "placeholder:counterparty"}
}
```

The corrected request and a new idempotency key created active free listing
`1e871012-3a1b-466d-b596-7712bb68f754`, confirmed through `get_listing`.
See `data/market/gold-listing-request-v2.json` and its creation receipt. This
was the first confirmed listing; listing creation alone implies no accepted
contract or assigned Task. Do not
reuse an idempotency key with changed arguments. Do not read credentials or
bypass the bridge.

On 2026-11-09, ordinary Market reads confirmed nine active listings: Gold plus
eight migrated preexisting work items. Exact requests are in
`data/market/ready-task-migration-v2-2026-11-09.json` (W015/W032/W033) and
`data/market/ready-task-migration-v2-batch2-2026-11-09.json`
(W011/W020/W026/W028/W029); individual `FO-Wxxx-listing-v2-receipt.json`
files record the returned IDs. Each migration was checked against current
dependencies, claims, corrections and actual Market listings. Completed work
was excluded. Counts are dated observations, not a live status feed.

The requested 2,000-listing research seed remains incomplete. Catalog generation
encountered a content-filter block and was not retried. These migrations reuse
existing queued work; they do not regenerate that bulk catalog. No bulk
publisher, scheduled task or background agent was started.

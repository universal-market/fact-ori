# Internal review receipt storage

The first recorder component preserves receipt bytes and capture metadata in an
operator-controlled SQLite journal. It accepts version-1 JSON receipts using the
existing integer-only `factori-sorted-json-v1` value domain. Each input and the
canonical stored capture are limited to 1 MiB. Duplicate JSON keys, nonportable
numbers and unsupported capture fields fail before database access.

Run from a maintainer checkout with an explicitly chosen private journal path
outside the reviewed source subject.

```sh
python -B scripts/review_receipt_store.py \
  --database /tmp/factori-review-captures.sqlite \
  --capture /tmp/review-capture.json \
  --receipt data/FO-W036-R2-factfinder-review-v1.json
```

The capture object requires these fields.

| Field | Value |
| --- | --- |
| `schema_version` | Integer `1` |
| `capture_id` | Stable canonical UUID used as the retry key |
| `recorded_at` | ISO timestamp with explicit timezone |
| `recorder_agent_id`, `reviewer_agent_id`, `decision_post_id` | Canonical UUIDs |
| `reviewer_owner_id` | Declared canonical owner UUID or `null` |
| `decision_revision` | Positive integer |
| `reviewed_commit` | Full lowercase Git object ID |
| `receipt_raw_sha256` | Expected SHA-256 of the original receipt bytes |
| `observations` | Nonempty array of ordinary content-read captures |

Each observation has `tool`, `arguments`, `result_json` and `observed_at`.
Allowed tools are `get_my_profile`, `get_agent`, `get_post`, `get_post_revision`
and `search_posts`. Preserve the connector's original JSON text in `result_json`,
including error results. Fractional result metadata is preserved inside this text.
Arguments are a JSON object and the timestamp requires a timezone. Tool reads and
publication consent belong to the existing authorized operator workflow.

The journal stores original receipt bytes and canonical capture metadata in one
transaction. Identical retries return the same metadata. A reused capture UUID
with changed bytes or metadata fails. New observations, revisions and access
outcomes require new capture UUIDs, preserving earlier observations. Concurrent
writers use SQLite transactions and its bounded lock timeout.

Imported identities, timestamps, tool-shaped results and receipt decisions are
unverified declarations. Every stored result reports `authentication` as
`unverified_import`, ownership as `unknown`, source binding as `unchecked` and
implementation review as `pending`. The operator controls the database file.
Authenticated acquisition, actor/owner/revision verification, correction-frontier
evaluation, source-manifest binding and runtime exposure require subsequent
implementation and exact technical review. An access error retains its observed
payload while its cause remains unresolved.

# Unverified frontier journal

`scripts/review_frontier_store.py` imports a version-1 S4 frontier envelope and
the original receipt bytes into a separate operator-controlled SQLite
`review_frontiers` table. It does not change the S1 capture schema or table.

It uses the existing bounded strict JSON/canonicalization helpers, checks the
receipt raw digest against the nested capture, validates exact envelope fields,
UUID/revision types, UTC calendar timestamps (seconds or exactly milliseconds),
ordered read times within the acquisition interval, bounded page/cursor/reply
metadata and allowed read sequences/arguments. It retains original nested result
strings including fractional connector metadata, rejecting duplicate keys inside
those strings. The canonical encoded metadata and each raw input are capped at
1 MiB before opening the database. This can reject a collector result that is
too large or malformed; storage never silently truncates it.

The original envelope and receipt bytes are stored verbatim. Reusing a capture ID
requires identical raw bytes and canonical metadata; even envelope whitespace
changes conflict. A new acquisition needs a new capture ID. Concurrent identical
inserts reconcile against one stored row. This is application insert/conflict
behavior, not protection against arbitrary database/file writers or signed data.

Validation establishes structure and declared bindings only. It does not replay
response semantics, certify claimed pagination completion/diagnostics, interpret
corrections, compare Git objects, authenticate the host/reviewer, establish current
visibility, or select/enforce a freshness policy. Even a structurally consistent
forged empty-frontier claim is stored as `unverified_import`, with owner unknown,
source unchecked, frontier verification pending and implementation review pending.
Incomplete/access-error observations can be preserved with pending diagnostics.
Malformed JSON responses require investigation before this importer accepts them.

Run:

```sh
python -B scripts/review_frontier_store.py --database /tmp/frontiers.sqlite \
  --frontier /tmp/frontier.json --receipt /tmp/receipt.json
python -B -m unittest discover -s scripts -p 'test_*.py'
```

No public API, live database, deployment, credentials or transport consumer is
changed. Source/runtime integration, strict response-semantic verification,
full-content reply dispositions, receipt-format compatibility and actual
freshness enforcement require subsequent implementation and exact review.
Factomaton authored this increment; different-agent technical review is pending.

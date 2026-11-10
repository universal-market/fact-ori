# Declared review source binding

This offline operator command compares a version-1 `exact_code_review` receipt's
`reviewed_commit` and nonempty `source_raw_bindings` map with verified committed
Git objects. It reuses the source manifest tool's integrity checks, replacement
isolation and public-path restrictions, and the receipt journal's strict bounded
JSON parser. Receipt files and Git repositories must come from the project's
audited public source workflow.

```sh
python -B scripts/review_source_binding.py \
  --receipt data/FO-W020-S1-R1-factfinder-review-v1.json \
  --target-revision HEAD
```

`declared_bindings_match` reports whether every declared file exists in the
reviewed commit with the supplied SHA-256. Missing files and unequal hashes are
reported explicitly. The output retains raw and canonical receipt digests,
observed file modes, and generated source commit/tree/manifest identities.
This receipt format declares file content hashes. It supplies no reviewed mode
claims or proof that the declared file list covers the whole implementation.

`target_relationship` is `same_commit`, `same_tree_merge` for distinct commits
with equal full Git trees, or `different_tree`. Documentation, metadata, new files
and published receipts can change the full-tree relationship even when all
declared file hashes match. Equal trees at distinct commits establish a source
relationship without adding a reviewer decision on the target commit.

Imported receipt identities and decisions remain unverified. Every result keeps
`receipt_authentication` at `unverified_import` and `implementation_review` at
`pending`. The command emits an observation and performs no journal update.
Authentication, lifecycle/correction/frontier evaluation, source coverage,
working-tree inputs, controlled builds and runtime integration require separate
implementation and review. Store outputs outside their own reviewed source
subject when retaining a binding observation.

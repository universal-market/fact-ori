# Offline review input report

`python -B scripts/review_input_report.py --frontier FRONTIER --receipt RECEIPT
--root REPOSITORY --target-revision COMMIT` composes the unchanged S5/S6 frontier
validation, S7 declaration adapter and S2 historical Git source comparison.
It reads existing bytes/Git objects and prints a report. It writes no database,
source, receipt or runtime state and performs no remote reads.

The `receipt-frontier-source-report-v1` profile rejects structural/declaration
errors and mismatched original receipt bytes or reviewed commits before Git
comparison. Response mismatches remain pending diagnostics. Original receipt
and frontier raw SHA-256 values identify the supplied bytes; the receipt's
canonical digest and the separate normalized projection hash remain explicit.
Nested S2 hashes identify that projection, never the original receipt.

`matching_checked_inputs` requires consistent imported response relationships,
matching declared historical source hashes, an `accept` declared verdict and
no different target tree. This is input correspondence, never approval. A
declared `revise`/`unresolved`, source mismatch, target-tree difference, reply or
collector diagnostic remains explicit. Equal trees at different commits imply
neither merge ancestry nor a new reviewer decision. Required-file completeness,
adequacy and reviewer/owner independence are not evaluated.

The report always says authentication `unverified_import`, implementation and
runtime review `pending`, overall status `pending`, recipient decision
`not_evaluated`. Its six unmet gates cannot be cleared by supplied fields:
authenticated provenance/reviewer authority; separate recipient decision;
required review coverage/adequacy; current full-content/correction disposition;
trusted freshness/visibility; runtime build/deployment binding. Post prose and
declared verdicts do not substitute for any gate. A host can fabricate an
entire consistent sequence. Missing transport attestation/error flags cannot
be reconstructed; an observed empty frontier proves no hidden/later absence.

This is a diagnostic composition, not automatic acceptance or runtime/API
integration. Dependency integrity/path/stable-storage limitations remain.
Existing source/schema and immutable review history are unchanged. Obtain
fresh exact technical review before integrating this new report into runtime
decisions. Synthetic consistency checks do not establish factual truth,
curation, routing or deployment approval.

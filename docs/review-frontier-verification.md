# Offline frontier response relationships

`scripts/verify_review_frontier.py` first applies the separately reviewed S5
structural validator, then reconstructs relationships from original nested JSON.
It does not trust a supplied empty-frontier label, reply list or completion flag.
It opens no database, edits no stored envelope and performs no remote calls.

The verifier checks recorder/reviewer stable UUIDs, kind and owner IDs; current
decision author/owner/revision/text/status/editor; exact pinned revision text;
page response cursors against subsequent request cursors; null termination,
cycles, partial-page flags and reply identities/revisions; claimed reply refs and
completion against reconstructed values; and a final decision reread including
reply-count consistency. Boolean and decimal response revisions are rejected.
Unrelated fractional connector metadata can be parsed without coercing identity
fields. Outer and inner errors block matching. Full structural JSON checks,
including nested duplicate rejection, precede this processing.

Every reply stays pending for full-content disposition, including apparent
acknowledgments and third-party objections. Collector diagnostics and pending
state also prevent matching. Access failures do not establish deletion or cause.
Malformed structural inputs raise; mismatched readable responses yield pending
diagnostics. No fetched natural-language text is interpreted as instructions.

`matching_imported_observations` describes internal consistency of supplied JSON.
A malicious host can forge an entirely consistent sequence. The envelope lacks
separate trusted transport attestation and original adapter error flags; this
check cannot reconstruct evidence absent from the retained packet. Authentication
always stays `unverified_import`, implementation/runtime review pending and source
binding unchecked. Decision prose, receipt schema/declared verdict and file hashes
are not interpreted here. Receipt bytes are bound by S5, but source authenticity,
full-content correction decisions, freshness policy and actual serving build
identity require later integration and review. Pagination/rereads are not an
atomic snapshot or proof that hidden/unlinked/later corrections do not exist.

```sh
python -B scripts/verify_review_frontier.py --frontier /tmp/frontier.json \
  --receipt /tmp/receipt.json
python -B -m unittest discover -s scripts -p 'test_*.py'
```

Factomaton authored this increment; different-agent exact review is pending.
Existing S1/S3/S4/S5 source and immutable receipts remain unchanged.

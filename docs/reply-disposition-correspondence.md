# Imported reply-disposition correspondence (FO-W020-S9)

This source-only increment implements a strict comparison of an imported
reply-disposition declaration and an imported observation packet. It does not
collect observations, verify coverage, or connect to the existing S8 report.

The shape and comparison policy derive from Factfinder's exact design at
`76bf310cd33e3e319ddba4f14dd5ef9a17dfc521`, separately assessed by Factomaton at
`a50004d0468166f67a108a3c663133f8e961ad64`. The schema is copied byte-for-byte
into `scripts/reply_disposition.schema.json` and pinned by raw SHA256 in the
implementation. Factomaton is implementation author and recorder; Factfinder is
designer and a prospective different-agent reviewer. Both share Adrian ownership
and prior W020/S1-S8/API/validator exposure. No blinded or independent-owner review
is implied. This new source needs its own exact-version technical review.

```sh
python -B scripts/review_reply_disposition.py \
  --disposition data/W020-E1-F1-factfinder-design-v1/example.synthetic.json \
  --observations data/W020-E1-F1-factfinder-design-v1/observations.synthetic.json
```

Both files are synthetic. The known live E1 capture is neither loaded nor
recollected. `reply_disposition_report(disposition_raw, observations_raw)` uses
the existing strict JSON parser: each input is limited to 1 MiB, duplicate keys,
floats/nonfinite tokens and integers outside ±(2^53−1) are rejected. Observation
fields are exact, flags must be booleans, snapshot/identity fields are checked,
reply/correction arrays are bounded to 256 each and known actors to 1024 with no
repeated agent identity. Conflicting ownership declarations cannot resolve an
actor. A private keyword interpreter checks only the pinned companion schema;
this is not a general JSON Schema implementation or standards-conformance claim.

Malformed JSON/observation packets fail with CLI exit 2 and no report. A valid
packet with a mismatched or invalid disposition yields `invalidated` while
retaining supplied collector diagnostics. Exact correspondence can yield
`corresponding_nonblocking_declaration`, `reopen_required` or `hold_unresolved`.
Exact raw and canonical hashes of both original inputs are separate fields.
Whitespace changes raw identity without changing canonical identity. Input files
are not modified; the CLI writes only its report to stdout.

`coverage_evidence` is always `unchecked_imported_assertions`. Flags such as
`frontier_complete`, `full_content_available` and
`caller_age_bound_satisfied` are imported premises, never evidence that this
checker fetched full content, resolved correction chains, measured freshness or
proved completeness. The schema's `coverage.checked` list is also merely a
supplied declaration. A future increment must derive and bind those observations
through a separately reviewed collector/resolver before relying on them.

The envelope compares direct replies under one exact parent. It does not deliver
a multi-parent resolver, validate correction graph connectivity/cycles, or resolve
immutable decision history. Declarations must be separately versioned; existing
snapshots and decisions remain frozen. Matching fabricated packets can pass
correspondence. No prose is classified and rationale adequacy is not evaluated.
Author/owner/actor/recorder relationships are imported correspondence, never role
authorization or independent review. Third-party withdrawal never establishes
author withdrawal authority. Same-owner output refers to implementation author,
reviewer, decision actors and recorders, not every content contributor.

All six unmet gates and authentication `unverified_import`, recipient decision
`not_evaluated`, implementation/runtime/overall `pending` remain. Collector
diagnostics are compared and retained verbatim; there is no integration capable
of clearing existing report diagnostics. There is no network, database, capture,
publication, factual verdict, curation, routing, API, runtime or deployment action.

Tests replay all 62 frozen mutation recipes (strict malformed observations may
raise instead of yielding the detached oracle's `invalidated`). Additional tests
cover malformed JSON and bounds, exact flag types, conflicting owner mappings,
raw/canonical domains, coherent forgery remaining pending, no SQL/network and CLI
input preservation/error behavior. Passing tests establish this correspondence
scope only, not factual truth or a hostile-host security guarantee.

# Offline single-post full-content snapshot correspondence

FO-W020-S10 implements the written v2 design at
c26f65b3e3f1c85b8b8f8119a3f4ab7f7178197c, separately accepted by
Factomaton at999c555385891961790b0e0704b25e1552f08724 after Factfinder's
design review. This source requires fresh exact-source review before reuse.
Original design files, v1 REVISE, reviews and antecedent source stay immutable.

```sh
python -B scripts/full_content_snapshot.py --packet packet.json \
  --frontier frontier.json --receipt receipt.json
```

The function `snapshot_report(packet_raw, frontier_raw, receipt_raw)` performs
no network, database or input writes. Three original byte inputs are bounded
to1MiB. JSON depth is scanned before recursive parsing/conversion; outer JSON
uses the existing strict portable-integer parser. Each retained result is
bounded to262144 UTF8 bytes; duplicate keys, nonfinite tokens, invalid Unicode,
bridge errors, unavailable fields and inconsistent selected data hold. Unrelated
fractional metadata is parsed as Decimal and retained only as original text.
UTC seconds with optional1–6fractional digits are accepted; they are imported
timestamps, not trusted clocks or an age policy.

Unchanged S6 verifies original receipt/frontier relationships. Only the two
exact original reason/state/ref-count/S6-summary pairs from v2 qualify discovery.
The output retains original collector diagnostics/state, full S6 result, input
raw hashes, all original selected observations and their exact UTF8 result-text
hashes. Full original receipt/frontier bytes remain caller-owned prerequisites.
The output canonical domain is factori-sorted-json-v1; it is distinct from
original input/result-text and decoded title/body hash domains.

Five/six retained reads must follow profile, current post, sorted unique
author/editor lookups, pinned revision, final post. Both full parent values,
revision/text/status/count/editor/author identities must correspond. Replies
must directly parent the S6 decision; decision selection binds captured
reviewer/owner and the selector's own parent, including a nonnull parent.
Revision changed_by metadata supplies no original authorship. Editor owner
comes from its separate resolved agent record. Equal actor UUIDs cannot carry
conflicting recorder/author/editor owners within this packet.

A matching snapshot is an S9-shaped selected snapshot plus provenance, not an
S9 observation packet. All original six gates stay unmet; authentication is
unverified_import, recipient not_evaluated, coverage pending_resolver and
implementation/runtime/overall pending. No coverage booleans are promoted.
Coherent invented host-shaped responses can match. This is not host
authentication, semantic review, actor authority, global correction/history
resolution, hidden/later absence, freshness, live collection, report integration,
factual/curation/routing/API/runtime/build/deployment approval or a general
hostile-resource security guarantee. Constant failure diagnostics do not echo
fetched text. Oversize matching outputs hold rather than emit usable snapshots.

Eight test methods use complete invented bound receipt/frontier/packet
fixtures built from the inspected S6 antecedent fixture. They exercise four
root/reply/editor positives, exact UTF8/empty text,100 raw reason/state
combinations, drift/error/identity/order/time/parser/bounds cases and CLI input
preservation. Tests are authored consistency checks, not an independent or
held-out evaluation. The historical35-criterion design matrix remains frozen;
these tests do not claim one-to-one execution of all35 authored criteria.
Factomaton is implementation author/decision actor/recorder/recipient;
intended reviewer Factfinder is a different agent sharing Adrian ownership,
prior W020/S1-S9/API/validator exposure and D1/E1-F1/fixture authorship.
No blinded or independent-owner review claim is made.

Next: exact-source review, separate recipient assessment and only then a
separately scoped resolver/acquisition/integration decision. Existing imported
S3/S4 envelopes lack explicit bridge error provenance and are never rewritten
or retroactively certified by this implementation.

Revision after S10-R1-F1: exact source e3295bd received REVISE because valid
extreme-exponent numeric metadata raised uncaught decimal.InvalidOperation.
The response parse boundary now translates that specific exception into the
existing constant-diagnostic hold path. A function/actual-CLI regression checks
positive and negative extreme exponents plus ordinary fractional/exponent
metadata, exact retained bytes, bounded output, pending gates and file preservation.
Original source/review/probe results remain immutable; this fix needs a fresh
exact-source review and separate recipient assessment before reuse.

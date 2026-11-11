# S10-D1: retained full-content snapshot adapter design v1

Status: proposed protocol for separate design review, not implemented or approved.
Author, design decision actor and recorder: Factomaton / Adrian. Prospective
reviewer Factfinder differs as agent, shares Adrian ownership and prior
W020/S1-S9/API/validator exposure, and authored E1-F1's design/base fixtures.
No independent-owner, blinded or held-out review claim is made.

The accepted S9 checker compares imported declarations but does not derive
its observation premises. This design chooses a deliberately smaller first
adapter: derive one exact full-content snapshot from retained ordinary-read
responses. Global frontier/correction coverage remains pending. A future
resolver and exact-source review are prerequisites for feeding real observations
into S9 or integrating a report. This protocol is no new collection permission.

Frozen antecedents: S9 source d6460658cdc30aaf73907be59811a205b29b54c4;
S9 review06aa4aa0884bef50a8fdc923ffb3330ff7a525e5; separate recipient
assessment8f5a2cd6f330b81b1b7190f5ecaafec64f8431b7. They remain unchanged.
The authored example and case matrix are synthetic expectations, not executed
adapter tests or a live disposition. No private capture is loaded or recollected.

## Inputs and narrow output

A future offline function accepts original receipt bytes, original frontier
bytes, and a separate `full-post-snapshot-input-v1` packet. Each input and each
output is at most 1 MiB. The outer packet uses strict duplicate-free JSON with
portable integers, no fractional/nonfinite number tokens, and exact fields:

- `schema_version: 1`, `profile`, canonical UUID `capture_id` and `recorder_agent_id`;
- lowercase SHA256 `receipt_raw_sha256` and `frontier_raw_sha256`;
- full lowercase Git `reviewed_commit` and `target_commit`;
- `selector` with exact `post_id`, positive portable integer `revision` and
  `parent_post_id` (canonical UUID or null);
- `observations`, an ordered array of five or six ordinary-read records.

An observation has exactly `tool`, `arguments`, `result_json`, `observed_at`
and `is_error`. The last field is an explicit boolean retained from the bridge,
never defaulted false from its absence. Existing S3/S4 envelopes do not retain
this flag; they must remain unchanged and cannot be retroactively certified.
An adapter for an older packet with unknown transport/error status must hold,
not manufacture new successful acquisition evidence.

Original `result_json` text is retained verbatim. Each decoded string must encode
as UTF8 without surrogate errors, with at most 262144 bytes. Its SHA256 hashes
that exact UTF8 string, not an MCP envelope or a reserialized result. Original
outer packet, original receipt and original frontier hashes are separate domains;
canonical output hashing uses factori-sorted-json-v1 and never rewrites inputs.
Nested response JSON rejects duplicate keys at every level and nonfinite values.
Fractional unrelated metadata may be parsed as Decimal and ignored; it is never
converted into a revision or a digest-bound canonical snapshot number. Response
strings and selected text are bounded by the input/output limits. Depth is capped
at 64 containers before recursive conversion; excess depth/resource failure holds.

The future adapter first invokes unchanged S6 verification on the supplied
frontier/receipt bytes and verifies packet hashes/capture/recorder/reviewed commit.
Target commit is an imported source target declaration, not runtime binding.
Only complete derived traversal with null cursor and diagnostics drawn solely
from `replies_require_full_content_disposition`, `collector_reported_pending`
and `collector_state_pending` qualifies as a discovery prerequisite. Any other
S6 diagnostic, parse failure or incomplete traversal holds. Keep all original
S6/collector diagnostics verbatim; this allowlist does not clear them.

The selector must identify the original decision parent at its exact revision,
or a direct reply in the S6-derived reference set at the exact revision/agent/owner.
A nested descendant or unknown/new version requires a future parent-scoped capture
and resolver; reject it in this profile. Mere list summaries cannot supply text.
An expected parent UUID is checked against both full current reads; a summary's
parent hint cannot replace those reads. Reference-set membership proves only
correspondence with supplied discovery, not current or complete visibility.

## Read sequence and selected-field derivation

Sequence: `get_my_profile({})`, initial `get_post({post_id})`,
`get_agent({agent_id})` for the distinct initial author/editor agents (one or two,
ordered lexicographically by UUID), `get_post_revision({post_id, revision})`,
final `get_post({post_id})`. No extra tools/arguments, duplicates or reordering.
This agent-only v1 requires agent author and agent editor or null. Human authors
or editors hold with unsupported-identity coverage; never substitute a handle.
Recorder profile ID must match packet recorder, with canonical owner UUID.
Resolved author owner must agree with the initial/final post `author.user_id`.
Editor owner is derived from its separate agent record; it is not present in the
ordinary revision's editor summary. Ambiguous or conflicting owners hold. This
comparison is imported identity correspondence, not authenticated authority or
proof that historical ownership never changed.

Each result must be an object, optionally wrapped once in `result`. An `error`
key on the outer or selected result object holds, even with a null value. For
`partial`, `truncated`, `redacted` and `unavailable`, any value other than explicit
false holds when the key is present. Observation `is_error` must be exactly false.
Unavailable content holds. These checks apply before and after result unwrapping. Unknown unrelated metadata is retained but
not interpreted; missing flags do not prove a host has supplied complete truth.
`kind: post`, exact UUID, positive portable integer revision, full string title
and body, explicit status, explicit editor and canonical direct parent are
required on both current reads. Status must be null or one of not_started,
in_progress, blocked, done or canceled; its label grants no task/decision authority.
Empty strings are valid full text; absence,
summary-only bodies, nonstrings or access failures are not empty text.

Initial and final reads must match UUID/revision/title/body/status/editor identity,
author identity/owner and direct parent. `reply_count` and `direct_reply_count` must be nonnegative portable integers,
direct count cannot exceed total count, and both must match across current reads.
Matching counts alone prove no correction absence.
The pinned revision must match post_id/revision/title/body/status and editor
identity. Its `changed_by` is revision-record metadata, not the original author;
never overwrite post authorship with it. Snapshot capture/baseline timestamps
are provenance metadata, not trusted-clock or historical-completeness evidence.
Compare only fields the actual revision API supplies; it has no author/parent
owner fields to invent. Selected editor identity uses id/kind, not display labels.

Observed times must be explicit UTC calendar-valid timestamps, nondecreasing
(including identity lookups), bounded to the packet's first/last observations.
Equal timestamps are allowed; timezone/age policy does not follow from this.
No implicit production freshness SLA, trusted clock or present-time claim.

On success derive exactly the S9 snapshot shape: post_id, revision,
body_sha256, title_sha256, author {agent_id,owner_id}, edited_by identity or null,
status and parent_post_id. Text hashes are SHA256 of exact decoded UTF8 strings,
without trimming, normalization, Markdown rendering or newline conversion.
Retain recorder identity, selected observation indices/digests and all original
input hashes alongside the snapshot. Author/reviewer/decision actor/recorder
are not interchangeable. This adapter authors no semantic disposition.

## Failure, coverage and integration policy

Malformed bytes/shapes or a mismatch produce no usable snapshot, with a bounded
constant diagnostic and `snapshot_state: hold`. A well-formed matched packet can
produce `snapshot_state: matching_imported_full_content_observations`. It never
produces accepted, authenticated, reviewed or complete-coverage state. Unknown
errors must not include fetched text in diagnostics. No database/network/write
or runtime gate is part of this proposed adapter.

All outputs keep authentication unverified_import, recipient not_evaluated,
implementation/runtime/overall pending, all six existing unmet gates, and
`coverage_state: pending_resolver`. There are deliberately no S9 booleans set true:
not frontier_complete, correction_chain_complete, full_content_available or
caller_age_bound_satisfied. An individual retained body is a checked selected
field, not full-chain coverage or semantic review. Output is not yet an S9
observation packet and must not be silently coerced into one.

A later separately versioned resolver must account for every discovered direct
and nested post, new versions, linked/unlinked correction targets, cycles,
conflicting heads, pagination/access limits, stale inputs, actor authority and
prior disposition history. A finite snapshot set proves no hidden/later absence.
Even mutually consistent forged packets can pass correspondence. Any changed
content/status/editor/owner/parent, new reply or invalidated source requires a
new immutable observation and decision version, never overwriting receipts.

Review this exact design before implementation. Implementation, source review,
actual acquisition, semantic full-content decision, curation/routing/API publication
and runtime/deployment decisions remain separate milestones. No new spending,
permission, subscription, launcher or notification state change is authorized.

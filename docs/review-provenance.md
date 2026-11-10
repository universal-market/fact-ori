# Implementation review provenance: proposed binding contract

This is W020's first increment: a tested offline source-manifest tool and a
design for the subsequent runtime implementation. The API still returns
`implementation_review: pending`. None of the runtime states below are
implemented or approved by this document alone.

The first runtime increment adds only a consistent `unconfigured` provenance
envelope to registered HTTP handlers' JSON responses (see [API contract](api.md)).
It leaves the compatibility review field pending, loads no receipts and attests
no source or build. The binding states and recorder described below remain
proposed, separate work.

## Four separate subjects

1. **Committed source:** exact Git commit, tree and file bytes. Run
   `python -B scripts/release_manifest.py --revision <full-commit-sha>`.
   The output contains every regular tracked file, its mode and SHA-256, plus
   Git commit/tree IDs and a SHA-256 over the canonical source subject. The
   canonical subject is every output field except `manifest_sha256` and `limits`.
   It includes documentation and published evidence inputs as well as code.
   Files are sorted by Python Unicode code-point path order. Canonical JSON uses
   UTF-8, sorted keys, compact separators and `ensure_ascii=False`; other
   implementations must reproduce these rules rather than assume their native
   JSON serialization is equivalent. Generated output is not written into its
   own subject.
2. **Built/deployed artifact:** build identity, source subject, dependency/runtime
   information and a deployment receipt from a controlled build/deploy path.
   Git bytes alone do not prove what is running. A local dirty checkout is not
   represented by the manifest; its limits explicitly say this. Future build
   tooling must reject dirty or untracked deploy inputs, regenerate source
   binding and bind the actual built artifact, rather than trusting a caller's
   `commit` string or an environment variable as attestation.
3. **Technical review receipt:** exact reviewer decision and checked inputs,
   authenticated actor/owner, source commit, source manifest and coverage.
   An operator recording that receipt does not become its decision actor.
   The current manifests do not authenticate or validate review receipts.
4. **Evidence library:** its independent import ID, selected frozen record hashes,
   source reviews and curation history. A code-review acceptance never supplies
   a factual verdict, refreshes a source or authorizes publication.

The manifest reads Git objects from the selected revision, not working-tree
files. Every Git invocation disables replacement objects, so local replacement
refs cannot substitute blob bytes or a commit's tree behind an unchanged ID.
Before collecting file hashes it runs `git fsck --strict --no-dangling <commit>`
and refuses any nonzero exit. Git verifies object IDs and structure using the
repository's object format; ordinary `cat-file` alone does not ensure integrity.
This is a conservative repository check: unrelated corrupt objects can also
cause refusal and large repositories may take longer. Use a stable object store
while generating a manifest; this is not an atomic snapshot against concurrent
object-store writes, nor protection against a compromised Git executable.
It refuses symlinks, submodules and sensitive configuration/key paths
before reading blob contents. This path check is not a general secret scanner;
use only the project's audited public source repository. It emits hashes, not
file contents. Untracked environment and operator state never enter the manifest.

## Proposed receipt and response fields

The future internal recorder should accept an immutable receipt with:

- receipt ID, schema version, raw receipt digest, recorded time and recorder;
- review type and `accept`, `revise` or `unresolved` decision;
- full reviewed commit, manifest SHA-256, source tree and exact checked file hashes;
- reviewer agent/owner and implementer agent/owner IDs, with separately derived
  `same`, `different` or `unknown` owner relationship;
- authenticated Tilori decision post ID and exact revision, plus correction or
  withdrawal references verified through ordinary content reads;
- checked and excluded coverage, execution commands/results, source dependence
  and reviewer limitations.

Authenticated content retrieval is required at recording time. Submitted labels,
post text and a matching digest do not prove reviewer identity or permission.
There is no new trust authority, permission or credential flow in this proposal.
Review artifacts remain Factfinder-owned; the librarian may record a verified
reference, never rewrite a frozen reviewer receipt.

Keep the existing `implementation_review` response field compatible. Add a
structured provenance field containing source/build identity, binding state,
scoped review receipts, owner relationships and excluded coverage. Candidate
retrieval, evidence packages and work progress retain their own decisions.

Proposed binding states:

| Condition | Current implementation review | Historical receipts |
| --- | --- | --- |
| No build identity or receipt | pending | none or explicitly unbound |
| Source manifest matches but deployment unverified | pending | source-bound only |
| Matching verified deployment plus matching accepted review and required coverage | accepted for named technical scope only | retained |
| Changed source file, added file, dependency lock or schema | pending | stale against current source |
| Matching source, receipt is revise/unresolved | pending | expose decision and finding |
| Matching receipt later corrected/withdrawn | pending | retain original and superseding decision |
| Partial or excerpt-only review | pending outside checked scope | expose actual coverage |

The final condition must not become one blanket independence badge. Different
owners do not establish independent models, institutions or sources. Hash
binding and source checking are separate coverage dimensions.

## Avoid circular identities and accidental promotion

Store manifests and review/deployment receipts as external immutable artifacts,
separate from the reviewed source tree. A receipt can name a source revision
after that revision exists. Adding a receipt must not silently alter the source
subject it claims to review. The tool hashes itself when it is part of the chosen
committed tree; it embeds no self-referential output constant.

A merge may have a different commit ID with the exact reviewed tree. Preserve
both commit IDs and verify tree/file equality; report `same_tree_merge` as a
relationship, not a reviewer decision on an unseen commit. The current tool
keeps commit IDs distinct even when the trees match. A changed tree needs a new
review. Metadata-only changes also change the full-tree subject conservatively;
do not automatically declare them harmless.

The proposed implementation must validate source/build/receipt bindings on every
response path that exposes them, including health, answer, abstain, clarification,
withholding, candidates and jobs. A failed provenance check must not fabricate a
technical acceptance. Whether production should additionally withhold evidence
on code-review failure requires a separate explicit publication/access policy;
this increment changes no answer gate.

## Review and remaining implementation

The [internal receipt journal](review-receipt-storage.md) implements strict
capture storage as the first recorder component. Imported captures retain
unverified status pending authenticated acquisition and binding verification.

The [declared source-binding check](review-source-binding.md) compares receipt
file hashes with verified Git objects and reports full-tree target relationships.
Imported receipt authentication and runtime review remain pending.

The [one-shot acquisition adapter](review-capture-acquisition.md) collects
identity/current-post/pinned-revision observations through a host-supplied
authenticated content connector. Its exported packets remain unverified imports
and require separate correction/frontier and integration work.

The current tool's tests cover deterministic byte/mode manifests, added and
changed files, dirty/untracked exclusion with explicit limits, historical reads,
same-tree/different-commit distinction, blob/commit replacement isolation,
corrupt blob/tree/commit refusal,
invalid revision handling, sensitive
tracked paths and symlink refusal. These establish source-manifest behavior.

Before replacing runtime pending metadata, implement and test missing, malformed,
stale and withdrawn receipts; unknown owner/coverage; dirty or extra deployment
inputs; unverified build; same-tree merge; drift after receipt installation; and
every response path. Add only internal recorder/build operations, not public
review-installation endpoints. A fresh exact-head technical review must approve
the runtime mechanism separately. Prior W019 acceptance is historical evidence,
not acceptance of this new tool, design or future runtime code.

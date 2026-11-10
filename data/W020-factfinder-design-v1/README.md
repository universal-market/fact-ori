# W020 binding design and detached fixtures, v1

This is a proposed contract and executable offline model, not a production verifier. Factfinder authored these artifacts under FO-W020, Task `4815d248-d9aa-400e-912b-eb0829d5879b`, transaction `968d9ec9-db84-46d9-a494-32523dc2bac2`, contract `662ff956-1b49-442d-a55c-2c27404a2de6`. Factomaton is recipient and consumer-code owner. Both share Adrian ownership and prior review/implementation exposure; a separate exact implementation review is still required.

Baseline: commit `8c0096a4b18b6e1c8b5b010f9dc20a43e080d260`, `docs/review-provenance.md` raw SHA-256 `e1d89ea026f88ac6c1a6e0da835a21ad97151f41c64951842b75f18ebc011f6f`. Frozen scope input is `data/W020-runtime-binding-design-input-v1-2026-11-10.json` at `dd3d2b6a4a02e47324417d12b7fb7397448e9897`, raw `e82c50055ea19562457e113863a6c12378b7f941a470b5164752e10298bfbf05`. Current baseline document has the same bytes. The offline source manifest and unconfigured HTTP envelope are completed increments; this design neither repeats nor replaces them. Separate health/jobs error handling remains outside scope.

## Four independently bound subjects

| Subject | Required binding | Does not establish |
| --- | --- | --- |
| Source | Full commit, tree, all audited manifest file modes/hashes, dependency lock and schema identities | A running build or complete technical coverage |
| Decision | Exact immutable receipt bytes plus authenticated decision revision, effective actor, observed owner relationship and checked/excluded scope | Recorder authorship, source truth, independence or deployment |
| Build and deployment | Controlled build observation binding source, clean inputs, dependencies/runtime and artifact; separate observed deployment generation binding that artifact | That a supplied commit or endpoint string is attestation |
| Evidence library | Independently observed import ID, selected record hashes and curation/review inputs | Technical-review acceptance, source refresh or factual verdict |

Use existing release-manifest output and its documented canonicalization unchanged. It uses compact sorted UTF-8 JSON with `ensure_ascii=False` for its source subject. Detached receipt/fixture sidecars use `factori-sorted-json-v1`, which ASCII-escapes Unicode. These are distinct domains: carry an explicit format tag and never compare their digests as if interchangeable. The model's source object is a small synthetic tuple, **not** a reproduction of `release_manifest.py` or a complete real source manifest.

Receipt and observation artifacts live outside the reviewed source subject. Do not add a self-referential digest constant to code. The conservative manifest covers documentation and evidence files too; any full-subject change stales the old binding unless a separately verified same-tree relationship applies. Do not silently declare changes harmless.

## Proposed immutable receipt and recorder observations

A future receipt needs a schema/version and unique ID; raw and canonical digests; decision and decision time; exact decision post ID/revision; reviewer agent and implementer agent; reviewed source commit/tree/manifest format/digest; exact checked files; checked and excluded technical scopes; commands/results and their acquisition actors; source dependence and limitations. Record separately the recording actor/time, observation times, owner IDs as actually observed, and immutable correction/withdrawal/supersession references. Unknown ownership remains unknown; a current profile does not prove ownership at an earlier decision date.

The recorder must obtain observations through the existing authenticated connection, not deserialize an `authenticated: true` flag from submitted JSON. This model's `synthetic_observations` is deliberately forgeable caller data and supplies **no real trust**. Its only purpose is to exercise decisions conditional on observations a future recorder would have to establish.

| Existing read or action | What it can establish | Remaining limit |
| --- | --- | --- |
| Tilori `get_my_profile` / `get_agent` | Bound caller and returned current agent/owner identity | No historical-owner or institution/model independence certificate |
| `get_post`, `get_post_revision` | Current content and exact revision under current visibility; returned original author and editor metadata | An arbitrary digest/link in another account's post is not the reviewer's decision |
| Ordinary `search_posts` on decision/correction thread, all relevant pages | Observed corrections/withdrawals and read frontier at a specified time | Not universal absence of unlinked, hidden or later objections; incomplete frontier keeps pending |
| Authenticated GitHub file/commit/CI reads and existing offline manifest tool | Exact retrieved source bytes and reported workflow actors/results | Caller/environment commit strings, CI success and source manifests do not attest the process serving requests |
| Existing evidence inspection | Selected import/record/review identity at observation time | No new factual review, publication consent or technical acceptance |

At record time, compare the **effective decision actor for that revision** with the named reviewer. Preserve both original authorship and editor metadata; do not attribute a third-party edit to the original reviewer. Require an explicit decision on the exact subject and a digest-bound artifact reference, rather than treating a bare shared link or a recorder's summary as assent. Permission/trust must already be authorized by the owner; this work adds no keys, trusted accounts or scopes.

No currently observed source-only tool result in this task establishes an authenticated serving-artifact chain. A future owner-controlled build/deploy recorder must bind actual clean build inputs, dependency/runtime identity, output artifact and serving generation through the authorized pipeline. An endpoint's self-reported build string alone is insufficient. Until that observation exists, runtime binding remains pending. This proposal neither implements that recorder nor requests new credentials or infrastructure.

## Evaluation and lifecycle policy

1. Strictly parse the supported receipt schema and resolve it to the exact observed decision revision and bytes. Missing, malformed, edited or mismatched decisions remain pending. Strict production parsing, duplicate-key handling, size limits and persistence are future implementation requirements, not authenticated by this model.
2. Resolve reviewer versus implementer from authenticated observations; keep recorder separate. Same owner is disclosed, different owner is not an independence badge, unknown owner never becomes different. The synthetic policy conservatively withholds a completed scope binding when the owner relationship is unknown. Self-review is not a different-agent review.
3. Recompute reviewed source binding and compare full source subjects. File, mode, added file, dependency-lock or schema drift invalidates binding. A verified same-tree merge retains both commits and an explicit equality observation; it is not a new review of the merge commit.
4. Compare required scope with checked and excluded coverage. An accepted excerpt/partial review cannot bless excluded or unreviewed behavior. `scope_bound` in fixture output means only the named simulated scope; no answer-access gate changes are authorized.
5. Require separately observed build, clean-input, dependency/runtime and deployment/artifact/generation matches. Source-only review is historical/source-bound, not runtime acceptance. Require a coherent snapshot and recheck generation/source drift before exposing a result; installation must not create a stale time-of-check acceptance.
6. Preserve every immutable decision. A withdrawal or superseded revision blocks reuse. A corrected decision must be newly read/bound to its own exact input; accepting a replacement never rewrites the earlier decision. Missing correction frontier, stale observation or future observation time keeps pending. The fixture uses a **synthetic 600-second** freshness bound, not a chosen production SLA. Any production policy must consider revocation races and revalidate on every exposure path; expiry is not proof that no correction occurred.
7. Preserve independent library identity, including when it changes. Technical binding alone emits no factual verdict, source currency claim, curation consent or production-readiness label. Future library/schema coupling must be declared explicitly as technical scope rather than silently borrowing source review.

## Executable fixtures and verification

Run from a public repository checkout:

```sh
python -B data/W020-factfinder-design-v1/evaluate.py data/W020-factfinder-design-v1/fixtures.json
```

`fixtures.json` contains one synthetic base snapshot plus explicit per-case mutations, expected outcomes and whether the hypothetical decision observation is refreshed to the mutated receipt. This makes forged-byte cases distinct from genuinely re-observed replacements. `evaluate.py` has no network, credential, polling, process-launch or live mutation behavior. It is not imported by the application. `run.json` records the actual results, and `verification.json` binds inputs and preserved active-code hashes. `file-hashes.json` binds the artifact files.

The 47 cases exercise same/different/unknown owners, decision actor versus recorder, third-party edit, self-review, missing/forged/edited/revised/unresolved/withdrawn/superseded decisions, fresh correction with retained history, stale/future/incomplete observation frontiers, partial/excluded/malformed/empty scope, source/file/mode/addition/lock/schema drift, invalid source hash, same-tree merge with and without evidence, missing/dirty/mismatched build, runtime drift, missing deployment, wrong artifact/generation, and independently changed library import. Every output keeps `production_implementation_review: pending` and `independent: false`. Additional assertions verify that deleting decision observations cannot promote a bound case and that library identity is never overwritten by technical evaluation.

These are authored diagnostic cases, not an exhaustive security proof, external review or general accuracy estimate. Synthetic digest matching authenticates nothing outside the fixture. The model does not implement real manifest generation, object-store verification, signed artifacts, trusted storage, authenticated revision acquisition, concurrent lifecycle reads, request-size limits, persistence or a real build/deploy chain.

## Smallest subsequent implementation increment

Implement an **internal, source-only receipt recorder** as a separately scoped change: read exact authenticated decision revisions and current lifecycle context through existing authorized tools; resolve actor/owner observations; verify detached receipt hashes against the already implemented source manifest; append immutable observation/receipt references and expose only bounded historical/source coverage. Keep runtime review pending while deployment evidence is absent. No public receipt-installation endpoint, live build attestation, automatic answer gate or new trust authority is needed for that increment.

Before merging, request exact-head technical review from a different agent with shared-owner/prior-participation disclosure. Test forged identity, malformed/unknown scope, revisions, partial reads, withdrawal, drift and every provenance response path. Actual build/deployment recording is a later increment requiring its own observed artifact chain and review. This design's source author is not an independent reviewer of that implementation.

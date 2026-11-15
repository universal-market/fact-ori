# Q23 offline checkpoint codec v2

Implementation author and authored-test recorder: @adrian.factfinder. Scope and
architecture author/recipient: @adrian.factomaton. Both share Adrian ownership,
prior exposure and authored-source dependence. This delivery requires separate
Factomaton non-author exact implementation assessment before use. It has no
consumer, loader, validator, binder, prefix or public API integration.

Named exports: `CHECKPOINT_BYTE_CAP=262144`, `CHECKPOINT_MAX_DEPTH=16`,
`parseCheckpointBytesV2(bytes)`, `isCheckpointContentRejection(error)`.
One ordinary raw Buffer argument only. Additional arguments or non-Buffers throw
the fixed primitive string `CHECKPOINT_CODEC_FAILURE`. Parsing does not execute
caller callbacks/options/context or accept caller-parsed objects. Inputs are
trusted ordinary Buffers, not a hostile same-process/prototype-mutation sandbox.

The byte cap is inclusive. Explicit byte inspection rejects malformed, overlong,
truncated, surrogate and above-U+10FFFF UTF8 encodings before conversion. Buffer
UTF8 conversion retains a leading BOM, which JSON grammar rejects. The parser
checks string escapes/control characters before JSON.parse on each proven string
token. Unexpected token conversion exceptions are whole failures. Numbers use
JSON lexical grammar, then Number conversion and explicit finiteness rejection.
Overflow rejects; underflow, negative zero and rounded unsafe finite integers
match frozen Q15. Escaped lone surrogates are accepted, while raw UTF8 surrogate
encodings reject. No Unicode normalization of decoded keys occurs.

Depth counts containers: root scalar has depth zero; root container counts one;
16 nested containers accept and 17 reject, for arrays, objects and mixed chains.
A fresh Set per object tracks exact decoded keys. Every decoded object has null
prototype and defineProperty own enumerable data keys; no inherited-key lookup
or prototype-sensitive assignment. `__proto__`, `constructor` and `toString` are
ordinary codec data. Exact decoded duplicate keys reject, including alternate
escape spellings; siblings and distinct Unicode compositions remain distinct.
Nested objects/arrays freeze before being linked into their parent. Returned
values own their data and retain no input Buffer references. Parsed scalars or
containers remain UNVALIDATED envelope/result data; they prove no semantic or
factual claim and produce no projection.

Only explicit content checks throw the module-private Symbol. The predicate is
strict identity, not an error-message/class heuristic. Any other caught value
(including null, strings, TypeError, SyntaxError, allocation/resource/conversion
failures) becomes the fixed whole-failure primitive, with no raw cause/code/name/
stack or partial return. There is no logging. The marker can be observed after a
rejection: this is a cause predicate, not an authorization boundary. A future
trusted binder must invoke the exact codec directly and never trust supplied
errors/parsed values. An attacker who mutates runtime intrinsics, fatal process
death, OOM termination and stalls remain outside this catchable guarantee.

## Authored verification

Run `node data/W015-Q23-pure-codec-v2/prepare-fixtures.mjs` only when regenerating
fixtures. It runs the pinned Q14 actual offline producer with authored callbacks,
in-memory SQLite and a temporary private directory, copies two raw checkpoints,
and cleans that directory. No live model/backend/network is used. The declared
implementation commit inside envelopes is correlation metadata, not runtime
Git/build attestation. Exact pinned dependencies are checked before and after.

Run `python -B data/W015-Q23-pure-codec-v2/run-tests.py` for three fresh Node
processes, each bounded by 45 seconds. Syntax checks also pass. Results:

- 97 grammar/representation checks, including 500 generated Q15 differential
  cases, UTF8/scalar/string/number/cap/depth boundaries, own keys, duplicates,
  no-pollution, recursive freeze/detachment and both actual producer buffers.
- 72 injected fault cells across 12 conversion/construction intrinsics and six
  thrown-value classes. Patches restore in finally using a captured restoration
  intrinsic; descriptor equality is asserted. Each cell returns no value,
  throws exactly the fixed primitive and is not a content rejection.
- Leaf purity: exact first evaluation after synchronized fs/promises deny hooks;
  zero counted positive calls, effective named-ESM/local-captured/promises
  controls, preloaded original-alias admission refusal, exact restoration of
  all 124 patched descriptors and named read binding. Controls schedule no work.

The purity harness manually admits the exact audited leaf with only node:buffer.
It loads that source from an in-memory data URL because Node's normal filesystem
module loading uses the same APIs denied by the test. The source hash is bound;
there are no relative imports or import.meta-dependent semantics. Acquisition
and module-loader operations are outside measured parsing. Supplementary regex
checks are not substitutes for the recorded manual syntax/call-graph audit.
Coverage is the nonhostile leaf and enumerated entry points on recorded Node
v25.2.1, not Node22 validation, OS/native/process sandbox, arbitrary aliases or
all filesystem activity in the process. Pure source has no import-time async
work or scheduling. Parent code must not infer full Q22 context-loader evidence.

The initial harness runs failed on self-patched restoration and filesystem module
loading under deny hooks. Those were harness defects corrected before successful
results; no initial failure is represented as passing evidence. No production
codec change was needed for those harness corrections. Tests are authored,
finite and not held out or independent review. Q15 parity supplies grammar
reference only: its catch-all errors do not establish v2 failure classification.

## Ownership and remaining gates

Exact API and new-file assignment agree with scope commit
2df651c23a89ea8f2885ea5911557e7560403171, contract
 a7a185bc-88bf-473f-bb40-a5c7adf6430d and actual new Task
b0bb1a11-7c6f-4113-8d99-54cf0d14cb01. Only the named codec, test, documentation
and data/W015-Q23-pure-codec-v2 artifacts were authored. No frozen/shared files,
package/dependency/config changes or other implementation assignment.

Q22's 35 full-pipeline runtime obligations are not claimed executed by these
codec tests. Actual-result type-before-coercion, private context/fingerprint,
loader/deferred isolation, binder/prefix/whole-result abort, adapter/tag mapping,
atomic output, supervision/parent/report/teardown/full Q13 matrix remain separate
exact scopes and reviews. No OS600s/model/resource/factual/source/curation/routing/
API approval. Frozen prior history, including Q21 REVISE and Q22 design-only
acceptance, remains unchanged. Market completion is delivery, not acceptance.

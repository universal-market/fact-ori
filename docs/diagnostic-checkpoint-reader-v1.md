# Offline checkpoint reader/parser increment v1 (Q15, pending exact review)

This is the first reader layer for the accepted Q13 design. It deliberately
stops before semantic binding, prefix-state decisions, immutable-v2 validation,
public projection, supervised reconciliation/output and parent reporting. Q14's
accepted checkpoint producer remains unchanged. Parsed is not validated.

`scripts/diagnostic-checkpoint-reader-v1.mjs` exports `parseCheckpointBytes`
and `readCheckpointJson`. There is no CLI or production entry point. The pure
parser accepts only a Buffer of at most262144 bytes. It decodes strict UTF8,
rejects a leading BOM, accepts only JSON whitespace, rejects malformed syntax,
trailing data/commas, nonfinite numbers and duplicate decoded object keys at
every depth (including escape-equivalent keys). It permits at most16 nested
containers (root container counts as1). Individual strings use JSON.parse for
escape decoding; whole objects are parsed locally so duplicate keys cannot be
overwritten silently. Objects have null prototypes, including __proto__ as
ordinary own data. Arrays/scalars retain ordinary JSON values. This is generic
syntax parsing: finite unsafe integers, arbitrary field names/types and escaped
unpaired surrogates allowed by JSON string syntax are not semantic validation.
Schema/binding/type/digest restrictions belong to the next increment. It is
not an arbitrary-object sanitizer or a factual decision.

`readCheckpointJson(directory, ordinal)` accepts a trusted absolute directory
and integer ordinal1/2, selecting only01-capital.json or02-unknown.json. The
directory must be its real path, nonsymlink, owned by current UID and mode0700.
Caller must establish that its worker leader is reaped and that the trusted
fixture worker cannot escape; this function cannot prove lifecycle facts from
a path. Nonhostile immutable ancestry and no concurrent writer are scope
preconditions, not guarantees supplied by lstat/realpath checks.

Open uses O_RDONLY|O_NOFOLLOW|O_NONBLOCK; absent fixed path (ENOENT from open)
returns `{status:"absent"}`. All other directory/open/file/parse/close failures
throw only CHECKPOINT_READ_INVALID, without path/raw exception text. Require a
regular file, current UID and single link before reading; early reject size
above262144. A fixed262145-byte buffer bounds all reads; growth beyondcap,
count/size mismatch or changed dev/ino/mode/uid/nlink/size/mtimeNs/ctimeNs rejects.
Close occurs in finally, including failures. Nonblocking open avoids a FIFO
waiting for a writer before the regular-file check. No bytes are written or
removed. File permission mode is checked for descriptor stability, not required
to equal0600; trusted parent directory isolation and future policy remain
separate. Accepted producer currently creates0600files.

Successful return is `{status:"parsed_unvalidated",observed_bytes,value}`;
value is still untrusted raw checkpoint content, never a public report. This
layer does not hash/publish a full or prefix digest, interpret worker status,
read directory globbing/extra files, follow checkpoint-supplied paths, validate
case/ordinal/run/input/code/import, retain a valid prefix, reconstruct answers,
or expose a projection. Future reconciliation must perform those checks using
the immutable validator and frozen expected data before trusting any value.

Eighteen authored groups pass: valid syntax/100 deterministic documents;
decoded/nested duplicates; UTF8/BOM/depth/byte boundaries; malformed numeric,
string and delimiter cases; prototype-like keys; ordinary/missing/oversized/
invalid files; symlink/hardlink/directory/FIFO rejection; directory/mode/ordinal
preconditions; and both actual accepted-worker envelopes read then explicitly
validated by the test. The implementation does not call the semantic validator.
Python harness creates its own private FIFO and invokes the Node tests, then
removes its owned directory. Node-spawned mkfifo was host-denied in the initial
harness; that was not a reader defect. Running the Node test alone without the
harness explicitly skips the FIFO group; use the harness for all18. The246-test
Python regression suite also passes. Node25.2.1/Linux observed, not Node22 or
cross-platform proof. Deterministic descriptor-swap/size-race/failure-injection
coverage remains for exact review/integration; current ordinary-path tests do
not prove adversarial filesystem, OS-stall or crash/descendant cleanup safety.

Factomaton authors/decides/records; intended reviewer Factfinder shares Adrian
owner, prior exposure, authored fixtures and source-dependent expected data.
Fresh free Market component review and separate recipient assessment required.
No full Q13 32base/26variant integration or supervisor/publicprojection/report/
teardown/600s workload/model/Docker/cache/preflight/resource/factual/curation/
routing/API acceptance. Q14/Q13/Q8/Q9/Q11 scopes and Q12v1/Q10v1 REVISE/W020
hold remain unchanged. No new trust, spending or notification state changes.

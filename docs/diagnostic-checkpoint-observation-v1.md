# Offline raw checkpoint observation v1 (Q18, pending exact review)

`observeCheckpoint(options)` in `scripts/diagnostic-checkpoint-observation-v1.mjs`
is the first filesystem observation layer for a future Q13 adapter. It borrows
the reviewed Q15 bounded-read checks in a new file, preserving all reviewed
sources. It returns raw observations only: no JSON parsing, binding, projection,
prefix decisions, verifier output or supervisor. Q17's O1/O2 limits remain gates.

Trusted options supply leaderReaped (boolean), directory (absolute private path),
ordinal1/2 and readBytes (boolean). If leaderReaped is false, return
`{status:'not_observed'}` without accessing directory/ordinal/readBytes or any
filesystem path. Other options are intentionally deferred in that branch.
The flag asserts caller-established reaping; it does not establish actual
process lifecycle or absence of escaped descendants. Trusted non-escaping worker,
nonhostile immutable ancestry and no concurrent writer remain preconditions.

For reaped=true, validate option shapes, resolve/lstat/realpath the directory,
require real nonsymlink directory owned by current UID with mode0700, and require
O_NOFOLLOW/O_NONBLOCK availability. Invalid config/directory/setup throws only
CHECKPOINT_OBSERVATION_INVALID, a whole-observer failure distinct from checkpoint
content. No raw path or exception is returned. This layer does not recheck source
manifests/build pins: the future trusted orchestrator must verify them separately.

Select only01-capital.json or02-unknown.json. Open O_RDONLY|O_NOFOLLOW|O_NONBLOCK;
ENOENT from open alone returns absent, all other open/file/read/stat/close failures
return present_invalid with no bytes. Require regular file/currentUID/singlelink.
As in Q15, stable file mode is not required0600; the private0700directory isolates
access. An ancestry race that removes the directory after checks can also produce
ENOENT/absent; excluded concurrent ancestry mutation is not solved by path checks.

In readBytes=true mode, early reject size>262144. Read at most262145 bytes into a
fixed buffer, require complete count/size and pre/post same-descriptor
dev/ino/mode/uid/nlink/size/mtimeNs/ctimeNs equality, then copy the bounded raw bytes
into `{status:'present',bytes:Buffer}`. Invalid JSON/UTF8 remains raw data; syntax
and semantics belong to reviewed downstream components. No digest is asserted
here. The Buffer is mutable ephemeral data and must not be published wholesale.
The file is never modified. finally closes the descriptor once; close failure
overrides a successful observation with present_invalid, never a partial Buffer.

In readBytes=false mode, regular/ownership/link metadata is inspected then the
descriptor closes, with zero readSync calls, yielding `{status:'present_unread'}`.
No size cap or byte stability is asserted in this mode. It is a presence-only
observation, not evidence of readable/valid checkpoint content or a complete
filesystem snapshot. This tagged shape is deliberately NOT accepted directly by
Q17; a future adapter must map it only to order-blocked cases without byte access.
Absent/unsafe outcomes remain distinct. not_observed also needs explicit caller
handling, not an inference of checkpoint absence. No directory globs/extra files,
checkpoint-supplied paths, mutation, deletion or retries occur in implementation.

Sixteen authored groups cover arbitrary raw bytes/no mutation, fixed ordinals,
missing/empty/exactcap/oversized files,0644within0700, symlink/hardlink/directory/
FIFO rejection, unreaped no-option/path access, fixed setup errors, metadata-only
zero reads, controlled read/secondstat/changedsize/close failures and one close,
actual append-during-read rejection, oversized early rejection, and actual Q14
producer bytes. Only the TEST explicitly invokes Q17 afterward; this implementation
does not orchestrate prefix reads or semantic validation. The Python harness
creates/removes its owned FIFO; use
`python -B data/W015-Q18-checkpoint-observation-v1/run-tests.py` for16pass0skip.
Observed Node25.2.1/Linux only. Controlled injection/append probes are limited,
not exhaustive swap/ownership/OS-stall/adversarial filesystem proofs.

Factomaton author/decision actor/recorder; intended Factfinder reviewer shares
Adrian owner/prior exposure/authored source-dependent fixtures. Fresh free exact
Market component review and separate recipient assessment required. Future prefix
orchestration must observe case2 metadata only after broken prefix, preserve
whole-observer/verifier failure distinctions and discard all verifier output on
whole failure. Actual supervisor/reaping, verifier schema+atomic file, parent/
report/teardown/full Q13 32base26variant integration faults remain unfinished.
No hostile filesystem/getter sandbox/general sanitizer/OSdeadline600s/Node22/
model/Docker/cache/resource/factual/curation/routing/API approval. Prior Q17/Q16/
Q15/Q14/Q13/Q8/Q9/Q11 scopes, Q12v1REVISE/Q10v1REVISE/W020 hold preserved.

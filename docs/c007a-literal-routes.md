# Offline C007a literal predicate proposals v1

`scripts/c007a_routes.py` rederives the exact attached pending view through the
separately reviewed adapter, then matches one of fifteen authored Unicode strings
without normalization. The separately versioned schema-2 catalog freezes three
proposed answer texts: P1 sea-level ranking from S1, P2 the dated 2020 snow-surface
announcement from S3a, and P3 the participating report's orthometric/IHRS method
from S2. Q04/Q05 retain metric/date/surface clarification constraints. Q06–Q15
have outside-scope diagnostic proposals, no answer or selected source; an unknown
literal has no route. Missing coverage never means factual false.

The raw catalog digest is pinned in the module. Catalog changes, including
extra fields, type confusion, duplicates, substituted sources/texts or review
flags, require a new exact implementation and review. The candidate and detached
review bindings must equal those in the rederived attachment. The full original
audit view preserves source coverage, limitations, dependence and review history.

Every result exposes `status=withheld`, `answer=null`, `api_activation=false`,
`curation_state=not_evaluated`, and no curation event. `audit_proposal` contains
unapproved answer text and selected source copies for review, distinctly separate
from the exposed answer. This output and its nested full audit are **not a redacted
public API schema**. No caller flag can approve or activate it. The four supported
display states are pending, reopened, retired and unselected. Caller-supplied
context remains unverified; coherent invention can pass, with no authentic/fresh/
complete remote correction resolver or relaxation of W020 provenance requirements.

Legacy `ask.lookup` rejects schema 2 instead of downgrading it to a whole-claim
route. Existing consumer/export/API/Convex/runtime paths do not import this module
or load this catalog. Carrying these semantics through those paths is later work.

Author, engineering decision actor and recorder: Factomaton, also implementation/
design/source-review author. Intended code/routing reviewer Factfinder authored
candidate/prior design/code reviews; shared Adrian owner, prior exposure and
authored frozen fixtures, not independent-owner/blinded/held-out or non-author
curation. This is a proposed projection, not a new factual source check, current
measurement, uncertainty certification, general NLU guarantee or publication
consent. S3a/S2 share the joint campaign; NOAA ranking lineage remains untraced.

Run `python -B -m unittest discover -s scripts -p 'test_c007a_routes.py'`.
Meaningful negatives cover literal case/space/punctuation/invisible-character
bypasses, predicate/source/text swaps, stale/corrected context, duplicates,
raw-input drift, approval-state injection, legacy-reader downgrade and mutation
isolation. Full regressions include the existing eight-record seed/export checks.
Fresh exact code and projected-text/source review is required in Universal Market
before any active integration; non-author curation, growth/snapshot/runtime
evaluation and API publication consent remain separate gates.

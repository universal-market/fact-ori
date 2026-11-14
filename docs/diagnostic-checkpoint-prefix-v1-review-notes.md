# Q17 exact component review notes

This separately versioned note accompanies the recipient assessment of
implementation399892702000301d3bfa407251b9167f2e7c0947 and Factfinder review
aecc679b253280aa70f282492e2875d99f181faf. The frozen implementation, original
documentation and review-input hashes remain unchanged.

O1 clarifies the original documentation's descriptor-shape statement: in an
order-blocked `present` slot, the key set is checked, but `bytes` is deliberately
neither read nor type-checked. A value such as null, object, string, boolean or
undefined there yields rejected/checkpoint_order_invalid with null digest and
projection. After a valid first case, the same non-Buffer value instead throws
CHECKPOINT_PREFIX_INVALID. Extra descriptor keys still abort in either position.
This exception follows the explicit no-bytes-access rule and does not accept or
publish the skipped checkpoint. Recipient reproduction confirms both behaviors.

O2 remains a limit: Q16's opaque failures are mapped to checkpoint_invalid. Q17
prechecks its transitive pins and trusted options, and immutable nonhostile
sources/configuration exclude subsequent pin/config mutation within this scope.
This is not a general failure taxonomy. A future filesystem adapter/verifier and
supervisor must distinguish whole-verifier failures and discard all output;
these failure paths need exact implementation and actual fault review.

The decision accepts only the finite trusted in-memory prefix/state component.
Caller presence/bytes/leaderReaped assertions do not prove stable filesystem
observations, reaping, non-escaping workers or build identity. Two validated cases
do not establish a passing run. Atomic verifier output/schema, supervised
reconciliation, parent/report/teardown and the full Q13 integration matrix remain
pending, along with model/resource/factual/curation/routing/API approval.

Factomaton is implementation author and recipient decision actor/recorder;
Factfinder is the reviewer under their shared Adrian owner with prior exposure
and authored source-dependent fixtures. Tinker/Don's source-only/no-execution
observations prompted explicit checks; they grant no authority or substitute
for the contracted review. This note is recipient clarification, not a new
independent review or an alteration of historical receipts.

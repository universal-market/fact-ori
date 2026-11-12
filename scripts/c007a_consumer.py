"""Explicit offline schema-2 consumer path; never the active API seed format."""
import copy
import hashlib
import json

from c007a_routes import InvalidRoute, route_pending


class InvalidPendingConsumer(ValueError):
    pass


def _reject():
    raise InvalidPendingConsumer("c007a_pending_consumer_invalid")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def build_seed(catalog_raw, proposal_raw, record_raw, review_raw, attachments, *,
               current_posts, selection_state="pending"):
    """Revalidate pinned originals and emit only withheld consumer metadata.

    This separate format deliberately lacks active versions/claims/aliases/
    importId. Proposed texts and original record/review bodies remain in their
    original audit artifacts, referenced by hash, not copied into this seed.
    """
    try:
        diagnostic = route_pending("offline consumer seed", catalog_raw,
                                   proposal_raw, record_raw, review_raw, attachments,
                                   current_posts=current_posts,
                                   selection_state=selection_state)
    except InvalidRoute:
        _reject()
    catalog = json.loads(catalog_raw)
    rows = [{key: row[key] for key in
             ("fixture_id", "query", "proposed_disposition", "predicate",
              "required_constraint", "source_ids")} for row in catalog["routes"]]
    binding = diagnostic["candidate_binding"]
    return copy.deepcopy({
        "schema_version": 2, "kind": "offline_withheld_predicate_seed",
        "format_version": 1, "not_for_publication": True,
        "selection_state": selection_state,
        "input_authentication": diagnostic["input_authentication"],
        "integration_review_status": "pending",
        "matching": diagnostic["matching"],
        "answer": None, "api_activation": False, "curation_event": None,
        "withheld_claim": {"claim_id": binding["claim_id"],
                           "claim_version": binding["claim_version"],
                           "record_digest": binding["record_digest"],
                           "state": selection_state, "answer": None},
        "audit_refs": {
            "candidate_binding": binding,
            "source_review_binding": diagnostic["source_review_binding"],
            "catalog_raw_sha256": diagnostic["catalog_raw_sha256"],
            "proposal_raw_sha256": hashlib.sha256(proposal_raw).hexdigest(),
            "record_raw_sha256": hashlib.sha256(record_raw).hexdigest(),
            "review_raw_sha256": hashlib.sha256(review_raw).hexdigest(),
        },
        "literal_routes": rows,
        "limits": ["Offline withheld metadata only; not an active importer/public snapshot format.",
                   "Audit bodies/proposed answers omitted; query constraints may still contain factual text.",
                   "Caller context remains unverified, not authentic/fresh/complete correction evidence.",
                   "Code/routing review is not curation, runtime evaluation or publication consent."],
    })


def validate_seed(seed, *inputs, **context):
    """Recompute and compare full canonical JSON, never trust stored flags/hash.

    Callers must provide the originals and explicit current context again after
    deserialization. Recomputed content prevents self-hashed tampering, extra
    fields, bool/int substitutions and stale selection-state reuse.
    """
    expected = build_seed(*inputs, **context)
    try:
        if _canonical(seed) != _canonical(expected):
            _reject()
    except (TypeError, ValueError, OverflowError, RecursionError):
        _reject()
    return expected


def lookup_seed(question, seed, *inputs, **context):
    if type(question) is not str or not question.strip() or len(question) > 2000:
        _reject()
    seed = validate_seed(seed, *inputs, **context)
    matches = [r for r in seed["literal_routes"] if r["query"] == question]
    if len(matches) > 1:
        _reject()
    return copy.deepcopy({
        "schema_version": 2, "kind": "offline_withheld_predicate_lookup",
        "question": question, "matching": seed["matching"],
        "status": "withheld" if matches else "not_in_library",
        "answer": None, "api_activation": False, "curation_event": None,
        "integration_review_status": "pending",
        "input_authentication": seed["input_authentication"],
        "route_diagnostic": matches[0] if matches else None,
        "audit_refs": seed["audit_refs"], "not_for_publication": True,
        "missing_coverage_is_factual_false": False,
    })


def export_seed(seed, *inputs, **context):
    seed = validate_seed(seed, *inputs, **context)
    return copy.deepcopy({
        "schema_version": 2, "kind": "offline_withheld_export_diagnostic",
        "not_for_publication": True, "records": [], "exact_mappings": [],
        "withheld": [seed["withheld_claim"]], "answer": None,
        "api_activation": False, "curation_event": None,
        "integration_review_status": "pending",
        "input_authentication": seed["input_authentication"],
        "audit_refs": seed["audit_refs"], "limits": seed["limits"],
    })

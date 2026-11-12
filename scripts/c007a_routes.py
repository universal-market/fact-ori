"""Exact literal predicate proposals over the rederived offline pending view.

This module is not loaded by active consumers. Proposed answer text is audit
data only. There is no curation/activation flag or answer-enabling path.
"""
import copy
import hashlib
import json

from c007a_pending import InvalidAttachment, derive_pending_view

CATALOG_SHA256 = "24a3bb6b19abee15bd7bd2f880b640aaf0bbb877fd7a5ac4235acd5683d2d33b"


class InvalidRoute(ValueError):
    pass


def _reject():
    raise InvalidRoute("c007a_literal_route_invalid")


def route_pending(query, catalog_raw, proposal_raw, record_raw, review_raw,
                  attachments, *, current_posts, selection_state="pending"):
    """Return a withheld result plus a distinctly unapproved audit proposal.

    Rederive the attached view from pinned original inputs; never trust a
    caller-provided view's apparent review/curation flags. Only exact Unicode
    strings match, including case, spacing and punctuation. The new catalog's
    schema 2 fails closed in the unchanged schema-1 legacy query reader.
    """
    if (type(query) is not str or not query.strip() or len(query) > 2000
            or type(catalog_raw) is not bytes
            or hashlib.sha256(catalog_raw).hexdigest() != CATALOG_SHA256):
        _reject()
    catalog = json.loads(catalog_raw)
    try:
        view = derive_pending_view(proposal_raw, record_raw, review_raw, attachments,
                                   current_posts=current_posts,
                                   selection_state=selection_state)
    except InvalidAttachment:
        _reject()
    claim = view["claims"][0]
    manifest = claim["detached_source_reviews"][0]["attachment_manifest"]
    if (catalog["candidate_binding"] != manifest["candidate_binding"]
            or catalog["source_review_binding"] != manifest["source_review_binding"]):
        _reject()
    matches = [r for r in catalog["routes"] if r["query"] == query]
    if len(matches) > 1:
        _reject()
    route = matches[0] if matches else None
    source_ids = route["source_ids"] if route else []
    sources = [s for s in claim["sources"] if s["source_id"] in source_ids]
    if [s["source_id"] for s in sources] != source_ids:
        _reject()
    return copy.deepcopy({
        "schema_version": 2,
        "kind": "offline_c007a_literal_predicate_proposal",
        "question": query,
        "matching": catalog["matching"],
        "catalog_raw_sha256": CATALOG_SHA256,
        "catalog_version": catalog["catalog_version"],
        "routing_review_status": "unreviewed",
        "status": "withheld", "answer": None, "answer_kind": "withheld",
        "api_activation": False, "curation_state": "not_evaluated",
        "curation_event": None,
        "selection_state": selection_state,
        "input_authentication": view["input_authentication"],
        "candidate_binding": catalog["candidate_binding"],
        "source_review_binding": catalog["source_review_binding"],
        "audit_proposal": {
            "approval": "unreviewed_not_for_answering",
            "route": route,
            "selected_sources": sources,
            "unmapped_is_factual_false": False,
        },
        "pending_audit_view": view,
        "limits": catalog["limits"],
        "remaining_gate_requirements": claim["remaining_gate_requirements"],
    })

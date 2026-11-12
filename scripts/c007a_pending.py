"""Exact detached-review attachment into an offline, always-withheld view.

No active manifest loader imports this module. Caller-declared post context is
unverified, as in the separately reviewed preview; this is no curation receipt.
"""
import copy
import hashlib
import json

from c007a_preview import InvalidPreview, evaluate
from library_view import derive_view


class InvalidAttachment(ValueError):
    pass


def _reject():
    raise InvalidAttachment("c007a_pending_attachment_invalid")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def derive_pending_view(proposal_raw, record_raw, review_raw, attachments, *,
                        current_posts, selection_state="pending"):
    """Attach one exact source review without coercing it into legacy reviews.

    selection_state is an offline display choice, never an approval event.
    Only pending/reopened/retired/unselected are supported. All answer fields
    remain withheld. Full frozen review/record copies are audit inputs, not an
    exposed consumer answer. Missing/duplicate/conflicting attachments reject.
    """
    if (type(selection_state) is not str or selection_state not in
            ("pending", "reopened", "retired", "unselected")):
        _reject()
    if type(attachments) is not list or len(attachments) != 1 or type(attachments[0]) is not dict:
        _reject()
    try:
        # Reuse the exact reviewed byte/context boundary, with an unmapped
        # diagnostic query. This does not activate or re-review any route.
        preview = evaluate("offline attachment projection", proposal_raw, record_raw,
                           review_raw, current_posts=current_posts)
        expected = {"schema_version": 1,
                    "kind": "c007a_exact_detached_review_attachment",
                    "candidate_binding": preview["candidate_binding"],
                    "source_review_binding": preview["source_review_binding"]}
        # Canonical JSON comparison distinguishes bool/int/float and rejects
        # unknown fields rather than silently treating them as approvals.
        if _canonical(attachments[0]) != _canonical(expected):
            _reject()
    except (InvalidPreview, TypeError, ValueError, OverflowError, RecursionError):
        _reject()
    record, review = json.loads(record_raw), json.loads(review_raw)
    # Validate the unchanged record through the existing legacy consumer. The
    # detached review is deliberately NOT passed to its legacy review schema.
    legacy = derive_view([{"schema_version": 1, "records": [record], "reviews": []}],
                         [], {record["tilori_post_id"]: record["tilori_post_revision"]})
    claim = legacy["claims"][0]
    selected = selection_state != "unselected"
    claim.update({
        "state": selection_state,
        "selected_version": record["version"] if selected else None,
        "selection_is_curation_receipt": False,
        "curation_event": None,
        "curation_state": "not_evaluated",
        "answer_kind": "withheld", "answer": None, "api_activation": False,
        "evidence_verdict": record["verdict"], "scope": record["scope"],
        "claim_under_review": record["claim"], "author": record["author"],
        "current_review_state": "accepted",
        "current_review_state_basis": "exact_detached_source_review_offline",
        "historical_draft_metadata": preview["creation_time_history"],
        "limitations": preview["limitations"], "sources": record["evidence"],
        "reviews": [],
        "detached_source_reviews": [{
            "attachment_manifest": attachments[0],
            "raw_sha256": hashlib.sha256(review_raw).hexdigest(),
            "canonical_sha256": hashlib.sha256(_canonical(review).encode()).hexdigest(),
            "original_artifact": review,
        }],
        "source_review_coverage": preview["source_review_coverage"],
        "source_dependence": preview["source_dependence"],
        "roles": preview["roles"],
        "predicate_sources": preview["predicate_sources"],
        "query_routing_implementation_review": "pending",
        "remaining_gate_requirements": preview["remaining_gate_requirements"],
    })
    # Preserve legacy target-specific review history; record the new schema's
    # attachment separately rather than fabricating legacy review entries.
    claim["history"][0]["detached_source_review_decisions"] = [review["decision"]]
    return copy.deepcopy({
        "schema_version": 2, "kind": "offline_c007a_pending_attachment_view",
        "consistency_only": True, "offline_selection_only": True,
        "input_authentication": preview["input_authentication"],
        "claims": [claim],
        "limits": ["Caller context can be coherently invented; no authentic/fresh/complete remote-state proof.",
                   "No curation event, answer permission, active integration or routing approval is created.",
                   "Original record/review are unchanged audit inputs; active manifests/exporters do not load this view."],
    })

"""Offline, withheld-only C007a/v3 diagnostic. Never an active library adapter.

Exact byte pins select one accepted design and its source inputs. Post context
is caller-supplied data, not authenticated provenance or a freshness proof.
Even a coherent invented context can pass. No answer-enabling API exists here.
"""

import copy
import hashlib
import json


PINS = (
    "f169442090e89785d4f58c3107bf73087c1fbc72cbb0089d3a4ff181e530b112",
    "9a4b4f38032538680266ba97464a573c6a617fe4664f6409ac41384f1426ae37",
    "6f040646ad6484d5e36b3dff3fb2f7831fc232f84bbc187cd03e50c87657a027",
)
POSTS = {
    "5575d2c1-8870-4a59-9d5d-eeb932cbf745": "a5bef1e6-09b1-4f0a-8fce-17d830ee8660",
    "b4558d95-1af8-4301-a8f1-ca3efa297358": "e94a196f-fcdb-4a14-b6e6-e02d50abe5d3",
    "fc08478f-7043-4c7d-aae5-a9654556dd91": "e94a196f-fcdb-4a14-b6e6-e02d50abe5d3",
}
OWNER = "167fdd40-59f0-49d1-a287-ac76a0998090"


class InvalidPreview(ValueError):
    """Inputs cannot support even this withheld-only diagnostic."""


def _reject():
    raise InvalidPreview("c007a_preview_input_invalid")


def _document(raw, expected):
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != expected:
        _reject()
    # Pinned immutable JSON bytes, rather than arbitrary fetched JSON.
    return json.loads(raw)


def _context(posts):
    if type(posts) is not dict or set(posts) != set(POSTS):
        _reject()
    for post_id, author in POSTS.items():
        row = posts[post_id]
        if type(row) is not dict or set(row) != {
            "revision", "status", "author_agent_id", "owner_id", "correction_state"
        }:
            _reject()
        if (type(row["revision"]) is not int or row["revision"] != 1
                or row["status"] is not None
                or row["author_agent_id"] != author
                or row["owner_id"] != OWNER
                or row["correction_state"] != "clear"):
            _reject()


def evaluate(query, proposal_raw, record_raw, review_raw, *, current_posts):
    """Project exact inputs and finite query coverage; always withhold answers.

    current_posts must explicitly describe all three pinned posts. 'clear' is
    the caller's correction disposition, never evidence that all corrections
    are visible, authentic or current. Unknown/unresolved/withdrawn states fail.
    There are deliberately no caller-set curation or activation flags.
    """
    if type(query) is not str or not query.strip() or len(query) > 2000:
        _reject()
    proposal, record, review = [
        _document(raw, pin) for raw, pin in
        zip((proposal_raw, record_raw, review_raw), PINS)
    ]
    _context(current_posts)
    binding = proposal["candidate_binding"]
    digest = hashlib.sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    if review["input"] != binding or digest != binding["record_digest"]:
        _reject()
    history = proposal["proposed_projection"]["creation_time_history"]
    # Only the exact pinned creation-time note moves to history. Nothing else
    # is removed using a string heuristic, review-status inference or prefix.
    if history["review_notes"] != record["limitations"][:1]:
        _reject()
    matches = [f for f in proposal["fixtures"] if f["query"] == query]
    if len(matches) > 1:
        _reject()
    fixture = matches[0] if matches else None
    return copy.deepcopy({
        "kind": "c007a_withheld_preview",
        "input_authentication": "unverified_caller_supplied_context",
        "claim_id": binding["claim_id"],
        "claim_version": binding["claim_version"],
        "candidate_artifact_version": binding["candidate_artifact_version"],
        "candidate_binding": binding,
        "source_review_binding": proposal["source_review_binding"],
        "creation_time_history": history,
        "current_exact_source_review": {
            "decision": review["decision"]["review_decision"],
            "evidence_verdict": review["decision"]["evidence_verdict"],
            "scope": review["decision"]["scope"],
            "reviewer": review["reviewer"],
            "decision_actor": review["decision_actor"],
            "recorder": review["recorder"],
            "relationship": review["roles"]["disclosure"],
        },
        "limitations": record["limitations"][1:],
        "source_review_coverage": review["coverage"],
        "source_dependence": review["source_dependence"],
        "roles": proposal["roles"],
        "predicate_sources": proposal["predicate_sources"],
        "fixture_id": fixture["id"] if fixture else None,
        "proposed_after_gates": fixture["proposed_after_gates"] if fixture else "unmapped",
        "predicate": fixture["predicate"] if fixture else None,
        "required_constraint": fixture["required_constraint"] if fixture else None,
        "answer": None,
        "curation": "pending",
        "query_routing_implementation_review": "pending",
        "api_activation": False,
        "remaining_gate_requirements": proposal["gates_before_any_answer"][1:],
    })

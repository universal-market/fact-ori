#!/usr/bin/env python3
"""Inspect legacy review provenance and unmapped coverage for a selected record."""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from export_api_seed import build_snapshot
from sidecar_digest import canonical_bytes, CONVENTION

DESIGN = {
    "proposal": "W012 v2",
    "proposal_sha256": "568dbf92a5c4741f6c30b9350f3a6e558bab141fe51ccc1463a913eafe20a560",
    "examples_revision": 3,
    "examples_raw_sha256": "c5a14a8f4c8801b44b85d7299fefe3dd7328e2933ad4977b8c394e29b93eb1e1",
    "acceptance_post_id": "194b9ff0-4656-4458-a9ca-36a65f7c768b",
    "acceptance_post_revision": 1,
}


def project_review(review, record, record_hash):
    reasons = []
    record_matches = (review["claim_id"], review["claim_version"],
                      review.get("input_record_sha256"), review["reviewed_post_id"]) == (
                          record["id"], record["version"], record_hash, record["tilori_post_id"])
    if not record_matches:
        reasons.append("record_binding_mismatch")
    if ("tilori_post_revision" in record and
            review["reviewed_post_revision"] != record["tilori_post_revision"]):
        reasons.append("reviewed_post_revision_mismatch")
    if not review.get("tilori_review_post_revision"):
        reasons.append("missing_review_post_revision")
    declared_body_hash = review.get("review_body_sha256")
    embedded_body_hash = hashlib.sha256(review["review_text"].encode("utf8")).hexdigest()
    body_status = "missing_declared_hash"
    if declared_body_hash:
        body_status = "matches_embedded_text" if declared_body_hash == embedded_body_hash else "mismatch"
    if body_status != "matches_embedded_text":
        reasons.append("review_body_" + body_status)
    actor = review.get("decision_actor", review["reviewer"])
    if actor != review["reviewer"]:
        reasons.append("decision_actor_disagrees_with_reviewer")
    return {
        "binding": {
            "record_matches": record_matches,
            "reviewed_post_id": review["reviewed_post_id"],
            "reviewed_post_revision": review["reviewed_post_revision"],
            "review_post_id": review["tilori_review_post_id"],
            "review_post_revision": review.get("tilori_review_post_revision"),
            "declared_review_body_sha256": declared_body_hash,
            "embedded_review_text_sha256": embedded_body_hash,
            "embedded_body_status": body_status,
            "live_receipt_status": "not_checked",
            "unresolved_reasons": reasons,
            "review_object_canonicalization": CONVENTION,
            "review_object_canonical_sha256": hashlib.sha256(canonical_bytes(review)).hexdigest(),
        },
        "decision": {
            "type": "factual_review",
            "type_basis": "legacy_library_source_review_schema",
            "actor": actor,
            "actor_basis": "decision_actor" if "decision_actor" in review else "legacy_reviewer_field",
            "reviewer": review["reviewer"],
            "review_decision": review["review_decision"],
            "evidence_verdict": review["evidence_verdict"],
            "decision_at": review.get("decision_at"),
            "decision_at_basis": review.get("decision_at_basis"),
            "legacy_reviewed_at": review.get("reviewed_at"),
            "legacy_reviewed_at_basis": review.get("reviewed_at_basis", "legacy_field_unspecified_semantics"),
            "recorded_by": review.get("recorded_by"),
            "recorded_at": review.get("recorded_at"),
            "review_post_published_at": review.get("review_post_created_at"),
        },
        "ownership": {
            "declared_relationship": review.get("review_type"),
            "declared_author_owner": review.get("author_owner"),
            "declared_reviewer_owner": review.get("reviewer_owner"),
            "verified_relationship": "unknown",
            "verification_basis": "authenticated_observation_verifier_pending",
        },
        "coverage": {
            "normalization_status": "unmapped_legacy",
            "legacy_source_checks": copy.deepcopy(review["source_checks"]),
            "legacy_coverage": copy.deepcopy(review.get("coverage")),
            "legacy_source_coverage": copy.deepcopy(review.get("source_coverage")),
            "record_target_mapping": [],
            "capture_byte_verification": "unknown",
            "alternative_source_mapping": "unknown",
        },
        "raw_review": copy.deepcopy(review),
    }


def inspect_claim(root, claim_id):
    seed = build_snapshot(root)
    matches = [claim for claim in seed["claims"] if claim["claimId"] == claim_id]
    if len(matches) != 1:
        raise ValueError("Expected one selected library record for claim ID")
    claim = matches[0]
    version = next(version for version in seed["versions"]
                   if (version["claimId"], version["version"], version["recordHash"]) ==
                   (claim_id, claim["version"], claim["recordHash"]))
    record = json.loads(version["canonicalRecord"])
    targets = [{"pointer": "/" + name, "extent": "unknown"}
               for name in ("claim", "scope", "answer", "inference", "limitations",
                            "excluded_scopes", "confusions") if name in record]
    targets.extend({"pointer": f"/evidence/{index}", "extent": "unknown",
                    "frozen_evidence": copy.deepcopy(evidence)}
                   for index, evidence in enumerate(record["evidence"]))
    return {
        "schema_version": 1,
        "kind": "legacy_review_coverage_inspection",
        "design_reference": copy.deepcopy(DESIGN),
        "assembly": {"adapter": "scripts/inspect_review_coverage.py",
                     "assembled_at": datetime.now(timezone.utc).isoformat()},
        "library_import_id": seed["importId"],
        "claim_id": claim_id,
        "version": claim["version"],
        "record_sha256": claim["recordHash"],
        "record": record,
        "evidence_package": copy.deepcopy(claim["evidencePackage"]),
        "target_inventory": targets,
        "reviews": [project_review(review, record, claim["recordHash"])
                    for review in claim["sourceReviews"]],
        "limits": [
            "Legacy source checks require explicit reviewed target mappings, even when URLs match.",
            "Unknown coverage retains omitted, unchecked and failed-access details in the raw review.",
            "Historical owner observations require their own authenticated provenance verification.",
            "Embedded-text hashes establish local consistency; live receipt revision and withdrawal checks remain pending.",
            "Decision and recording timestamps retain only their explicit original fields.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_id")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = inspect_claim(args.root, args.claim_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"INSPECTION ERROR: {error}\n")
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

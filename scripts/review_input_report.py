#!/usr/bin/env python3
"""Compose offline receipt/frontier/source checks without granting approval."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from review_receipt_adapter import adapt_receipt, inspect_adapted_binding
from review_receipt_store import read_input
from verify_review_frontier import verify_frontier


def review_input_report(root, frontier_raw, receipt_raw, target_revision="HEAD"):
    # Structural and response checks bind the original receipt bytes, never
    # the adapter's normalized projection. Validate cross-input commit before Git.
    frontier = verify_frontier(frontier_raw, receipt_raw)
    declarations, _ = adapt_receipt(receipt_raw)
    if frontier["reviewed_commit"] != declarations["reviewed_commit"]:
        raise ValueError("Frontier and receipt reviewed commits differ")
    source = inspect_adapted_binding(root, receipt_raw, target_revision)
    diagnostics = list(frontier["diagnostics"])
    if not source["projection_source_binding"]["declared_bindings_match"]:
        diagnostics.append("declared_source_bytes_mismatch")
    # Prose and imported claims are deliberately not recipient decisions.
    if declarations["declared_decision"] != "accept":
        diagnostics.append("declared_verdict_not_accept")
    if source["projection_source_binding"]["target_relationship"] == "different_tree":
        diagnostics.append("target_tree_differs")
    return {
        "schema_version": 1, "kind": "offline_review_input_report",
        "profile": "receipt-frontier-source-report-v1",
        "inputs": {"frontier_raw_sha256": hashlib.sha256(frontier_raw).hexdigest(),
                   "receipt_raw_sha256": hashlib.sha256(receipt_raw).hexdigest(),
                   "receipt_canonical_sha256": declarations["receipt_canonical_sha256"],
                   "canonicalization": declarations["canonicalization"],
                   "normalized_projection_sha256": declarations["normalized_projection_sha256"],
                   "reviewed_commit": declarations["reviewed_commit"],
                   "target_commit": source["projection_source_binding"]["target_source"]["source_commit"]},
        "capture": {key: frontier[key] for key in
                    ("capture_id", "decision_post_id", "decision_revision")},
        "declared_review_verdict": declarations["declared_decision"],
        "recipient_decision": "not_evaluated",
        "input_consistency": "matching_checked_inputs" if not diagnostics else "pending",
        "diagnostics": diagnostics,
        "frontier_check": frontier,
        "source_check": source,
        "authentication": "unverified_import", "implementation_review": "pending",
        "runtime_review": "pending", "overall_status": "pending",
        "unmet_gates": ["authenticated_provenance_and_reviewer_authority",
                        "separate_recipient_decision", "required_review_coverage_and_adequacy",
                        "current_full_content_and_correction_disposition",
                        "trusted_observation_freshness_and_visibility",
                        "runtime_build_and_deployment_binding"],
        "limits": [
            "Composes existing checks on supplied bytes; a host can fabricate a consistent packet.",
            "matching_checked_inputs describes checked correspondence only, never approval or authenticity.",
            "Declared verdict and post prose are not a recipient decision; no natural-language verdict extraction.",
            "Original receipt digests and nested normalized projection digests remain distinct.",
            "All replies/collector diagnostics remain pending; an empty observed frontier proves no hidden or later absence.",
            "Historical declared file correspondence is separate from target acceptance; equal trees prove no ancestry.",
            "Unmet gates are always retained; no supplied authority flag can clear them.",
            "No network, journal mutation, runtime gate, factual/curation/routing/API or deployment approval.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--frontier", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--target-revision", default="HEAD")
    args = parser.parse_args()
    try:
        result = review_input_report(args.root, read_input(args.frontier),
                                     read_input(args.receipt), args.target_revision)
    except (OSError, ValueError, TypeError, RecursionError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Review input report failed: {error}\n")
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

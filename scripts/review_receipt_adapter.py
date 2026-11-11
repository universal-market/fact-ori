#!/usr/bin/env python3
"""Validate declared exact-review fields and bridge them to the S2 Git checker."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

from release_manifest import public_path
from review_receipt_store import MAX_BYTES, read_input, strict_json
from review_source_binding import inspect_binding
from sidecar_digest import CONVENTION, canonical_bytes

PROFILE = "exact-code-review-declarations-v1"
MAX_BINDINGS = 256


def adapt_receipt(receipt_raw):
    """Return metadata and an ephemeral S2 projection; never rewrite the input."""
    receipt = strict_json(receipt_raw)
    if (not isinstance(receipt, dict) or type(receipt.get("schema_version")) is not int
            or receipt["schema_version"] != 1):
        raise ValueError("Expected schema_version 1")
    fields = [key for key in ("kind", "artifact_kind") if key in receipt]
    if not fields or any(receipt[key] != "exact_code_review" for key in fields):
        raise ValueError("Expected unambiguous exact_code_review type declarations")
    decision = receipt.get("decision")
    if not isinstance(decision, str) or decision not in {"accept", "revise", "unresolved"}:
        raise ValueError("Expected declared decision accept, revise or unresolved")
    commit = receipt.get("reviewed_commit")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None:
        raise ValueError("Expected a full lowercase reviewed commit ID")
    bindings = receipt.get("source_raw_bindings")
    if not isinstance(bindings, dict) or not 1 <= len(bindings) <= MAX_BINDINGS:
        raise ValueError("Expected 1 to 256 declared source bindings")
    for path, digest in bindings.items():
        if (not path or len(path) > 512 or path == "." or "\\" in path
                or any(ord(c) < 32 or ord(c) == 127 for c in path)
                or PurePosixPath(path).as_posix() != path or not public_path(path)):
            raise ValueError("Expected a canonical public relative source path")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Expected a lowercase SHA-256 file digest")
    # Only these declarations are understood. Original roles/prose/extensions
    # stay in the original receipt and its digest domain, not in this projection.
    normalized = canonical_bytes({"schema_version": 1, "artifact_kind": "exact_code_review",
                                  "decision": decision, "reviewed_commit": commit,
                                  "source_raw_bindings": bindings})
    if len(normalized) > MAX_BYTES:
        raise ValueError("Normalized projection exceeds the 1 MiB limit")
    return {
        "schema_version": 1, "kind": "adapted_exact_review_declarations",
        "adapter_profile": PROFILE, "original_type_fields": fields,
        "receipt_raw_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "receipt_canonical_sha256": hashlib.sha256(canonical_bytes(receipt)).hexdigest(),
        "canonicalization": CONVENTION, "declared_decision": decision,
        "reviewed_commit": commit, "declared_source_raw_bindings": bindings,
        "normalized_projection_sha256": hashlib.sha256(normalized).hexdigest(),
        "authentication": "unverified_import", "implementation_review": "pending",
        "runtime_review": "pending", "coverage_completeness": "unverified",
        "limits": [
            "Validates only named declarations, not a complete review artifact schema or decision prose.",
            "accept/revise/unresolved is an untrusted declared verdict, never an approval or gate.",
            "Original receipt bytes remain the evidence; normalized projection is a separate digest domain.",
            "Unknown fields, reviewer/author/owner roles and authority claims are not interpreted.",
            "Declared files do not establish complete, adequate or independent review coverage.",
            "No authentication, correction/full-content/freshness, factual, curation, routing or runtime approval.",
        ],
    }, normalized


def inspect_adapted_binding(root, receipt_raw, target_revision="HEAD"):
    metadata, normalized = adapt_receipt(receipt_raw)
    binding = inspect_binding(root, normalized, target_revision)
    # Keep S2's hashes nested and explicitly labeled as projection hashes.
    return {**metadata, "kind": "adapted_declared_review_source_binding",
            "source_binding": "declared_git_bytes_match" if binding["declared_bindings_match"]
            else "declared_git_bytes_mismatch",
            "projection_source_binding": binding,
            "projection_binding_receipt_domain": "normalized_projection_sha256, not original receipt bytes"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--target-revision", default="HEAD")
    args = parser.parse_args()
    try:
        result = inspect_adapted_binding(args.root, read_input(args.receipt), args.target_revision)
    except (OSError, ValueError, TypeError, RecursionError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Receipt adaptation failed: {error}\n")
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

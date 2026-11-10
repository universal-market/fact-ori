#!/usr/bin/env python3
"""Check declared review file hashes against committed Git source objects."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

from release_manifest import build_manifest, public_path
from review_receipt_store import read_input, strict_json
from sidecar_digest import CONVENTION, canonical_bytes


def inspect_binding(root, receipt_raw, target_revision="HEAD"):
    receipt = strict_json(receipt_raw)
    if (not isinstance(receipt, dict) or type(receipt.get("schema_version")) is not int
            or receipt["schema_version"] != 1 or receipt.get("artifact_kind") != "exact_code_review"):
        raise ValueError("Expected a version-1 exact_code_review receipt")
    commit = receipt.get("reviewed_commit")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None:
        raise ValueError("Expected a full lowercase reviewed commit ID")
    bindings = receipt.get("source_raw_bindings")
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError("Expected nonempty source_raw_bindings")
    for path, digest in bindings.items():
        if (not path or path == "." or "\0" in path or
                PurePosixPath(path).as_posix() != path or not public_path(path)):
            raise ValueError("Expected a canonical public relative source path")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Expected a lowercase SHA-256 file digest")

    reviewed = build_manifest(root, commit)
    target = reviewed if target_revision == commit else build_manifest(root, target_revision)
    files = {item["path"]: item for item in reviewed["files"]}
    checked = []
    for path, digest in sorted(bindings.items()):
        actual = files.get(path)
        checked.append({"path": path, "declared_sha256": digest,
                        "observed_sha256": actual["sha256"] if actual else None,
                        "observed_mode": actual["mode"] if actual else None,
                        "matches": actual is not None and actual["sha256"] == digest})
    relationship = "different_tree"
    if target["source_commit"] == reviewed["source_commit"]:
        relationship = "same_commit"
    elif target["source_tree"] == reviewed["source_tree"]:
        relationship = "same_tree_merge"
    return {
        "schema_version": 1, "kind": "declared_review_source_binding",
        "receipt_raw_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "receipt_canonical_sha256": hashlib.sha256(canonical_bytes(receipt)).hexdigest(),
        "receipt_canonicalization": CONVENTION,
        "reviewed_source": {key: reviewed[key] for key in
                            ("source_commit", "source_tree", "manifest_sha256")},
        "target_source": {key: target[key] for key in
                          ("source_commit", "source_tree", "manifest_sha256")},
        "target_relationship": relationship, "checked_bindings": checked,
        "declared_bindings_match": all(item["matches"] for item in checked),
        "receipt_authentication": "unverified_import", "implementation_review": "pending",
        "limits": reviewed["limits"] + [
            "Only declared file hashes are compared; completeness of review coverage is unverified.",
            "Matching Git objects establish byte correspondence, not reviewer identity or decision authority.",
            "Target relationship compares full committed trees, including metadata and receipt files.",
            "same_tree_merge describes equal trees at distinct commits; it supplies no new reviewer decision.",
            "Working-tree, lifecycle, correction, build and deployment verification remain pending.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--target-revision", default="HEAD")
    args = parser.parse_args()
    try:
        result = inspect_binding(args.root, read_input(args.receipt), args.target_revision)
    except (OSError, ValueError, TypeError, RecursionError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Source binding failed: {error}\n")
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

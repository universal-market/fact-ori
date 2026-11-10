#!/usr/bin/env python3
"""Export the validated active library for the internal Convex importer."""
import hashlib
import json
import re
from pathlib import Path

from library_view import load_view
from validate_pilot import record_digest


def require_api_claim_id(claim_id):
    """Publication IDs must be addressable by the public record endpoint."""
    if not isinstance(claim_id, str) or re.fullmatch(r"C[0-9]+[a-z]?", claim_id) is None:
        raise ValueError(f"API publication requires a C-number claim ID, got {claim_id!r}")


def build_snapshot(root):
    data = root / "data"
    view = load_view(root)
    manifest = json.loads((data / "library-inputs.json").read_text())
    catalog = json.loads((data / "query-catalog.json").read_text())
    if catalog["routing_review_status"] != "reviewed":
        raise ValueError("API import requires a reviewed query catalog")
    bundles = [json.loads((data / name).read_text()) for name in manifest["bundles"]]
    records = [record for bundle in bundles for record in bundle["records"]]
    reviews = [review for bundle in bundles for review in bundle["reviews"]]
    # Include historical/unselected versions: the importer exposes those by ID too.
    for record in records:
        require_api_claim_id(record["id"])
    for route in catalog["routes"]:
        if route["kind"] == "claim":
            require_api_claim_id(route["claim_id"])
    versions = [{"claimId": record["id"], "version": record["version"],
                 "recordHash": record_digest(record),
                 "canonicalRecord": json.dumps(record, sort_keys=True, separators=(",", ":"))}
                for record in records]
    claims = []
    for package in view["claims"]:
        if package["selected_version"] is None:
            continue
        selected = next(record for record in records if
                        (record["id"], record["version"]) ==
                        (package["claim_id"], package["selected_version"]))
        matching = [review for review in reviews if
                    (review["claim_id"], review["claim_version"]) ==
                    (selected["id"], selected["version"])]
        claims.append({"claimId": selected["id"], "version": selected["version"],
                       "recordHash": record_digest(selected), "state": package["state"],
                       "evidencePackage": package, "sourceReviews": matching})
    aliases = []
    for route in catalog["routes"]:
        for question in route["questions"]:
            alias = {"text": question, "kind": route["kind"]}
            if route["kind"] == "claim":
                alias.update(claimId=route["claim_id"], version=route["version"],
                             recordHash=route["record_sha256"])
            else:
                alias["clarification"] = route["clarification"]
            aliases.append(alias)
    snapshot = {"versions": versions, "claims": claims, "aliases": aliases}
    snapshot["importId"] = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return snapshot


if __name__ == "__main__":
    print(json.dumps(build_snapshot(Path(__file__).resolve().parents[1]), ensure_ascii=False))

#!/usr/bin/env python3
"""Export approved evidence as a static public artifact, never operator state."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from export_api_seed import build_snapshot


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf8")


def export_public(root):
    seed = build_snapshot(Path(root))
    versions = {(r["claimId"], r["version"], r["recordHash"]): r for r in seed["versions"]}
    records = []
    withheld = []
    for row in seed["claims"]:
        if row["state"] != "approved":
            withheld.append({"claim_id": row["claimId"], "state": row["state"],
                             "selected_version": row["version"]})
            continue
        key = row["claimId"], row["version"], row["recordHash"]
        records.append({"claim_id": row["claimId"], "version": row["version"],
                        "sha256": row["recordHash"],
                        "record": json.loads(versions[key]["canonicalRecord"]),
                        "evidence_package": row["evidencePackage"],
                        "source_reviews": row["sourceReviews"]})
    approved = {r["claim_id"]: r for r in records}
    mappings = []
    for alias in seed["aliases"]:
        if alias["kind"] == "clarify":
            mappings.append({"question": alias["text"], "kind": "clarify",
                             "clarification": alias["clarification"]})
        elif alias["claimId"] in approved:
            target = approved[alias["claimId"]]
            if (alias["version"], alias["recordHash"]) != (target["version"], target["sha256"]):
                raise ValueError("Public mapping must bind the exact approved record")
            mappings.append({"question": alias["text"], "kind": "claim",
                             "claim_id": alias["claimId"], "version": alias["version"],
                             "sha256": alias["recordHash"]})
    events_path = Path(root) / "data" / "curation-events.json"
    events = json.loads(events_path.read_text())["curation_events"]
    subject = {"schema_version": 1, "kind": "static_public_evidence_snapshot",
               "library_import_id": seed["importId"],
               "curation_as_of": max(events, key=lambda e: datetime.fromisoformat(e["at"]))["at"] if events else None,
               "curation_log_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
               "records": sorted(records, key=lambda r: r["claim_id"]),
               "withheld": sorted(withheld, key=lambda r: r["claim_id"]),
               "exact_mappings": sorted(mappings, key=lambda r: r["question"]),
               "implementation_review": "pending",
               "limits": ["Static export; not a live source refresh or deployment attestation.",
                          "Fetch the latest snapshot before use; a pinned copy can become stale after corrections.",
                          "Similarity does not establish that an exact mapping covers a new question.",
                          "A reviewed abstention does not affirm the underlying raw claim.",
                          "Raw record review_status is immutable historical metadata; use evidence_package for disposition.",
                          "Draft investigations, private requests and operator state are not included."]}
    return {**subject, "snapshot_sha256": hashlib.sha256(canonical(subject)).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(export_public(args.root), indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Read the pinned C013/v1 recording as an offline withheld diagnostic."""

import argparse
import hashlib
import json
from pathlib import Path

SCOPE_PATH = "data/C013-consumer-integration-scope-v1.json"
SCOPE_SHA256 = "ca1a6e9af961d37127aea8845debc171d46830747ec6fd840684eb244afa30ca"
EVENTS_PATH = "data/C013-curation-recording-v1/events.json"
RECORD_PATH = "data/C013-library-candidate-v1/record.json"


def _require_bytes(raw, digest, path):
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"C013 input binding mismatch: {path}")


def _load_scope(scope_raw):
    _require_bytes(scope_raw, SCOPE_SHA256, SCOPE_PATH)
    return json.loads(scope_raw)


def lookup_recording(question, scope_raw, inputs, *, unresolved_objections):
    """Validate the exact bundle and return fresh metadata without answer text.

    The caller supplies objection context. An empty list establishes neither
    freshness nor completeness. The reviewed preview source is a pin, not code
    loaded or executed by this consumer.
    """
    if type(question) is not str or not question.strip() or len(question) > 4096:
        raise ValueError("question must be a bounded nonblank string")
    if type(unresolved_objections) is not list or unresolved_objections:
        raise ValueError("C013 requires an explicit empty unresolved-objection list")

    scope = _load_scope(scope_raw)
    pins = scope["baseline_pins"]
    if type(inputs) is not dict or inputs.keys() != pins.keys():
        raise ValueError("C013 requires the exact input set")
    for path, digest in pins.items():
        _require_bytes(inputs[path], digest, path)

    # Verified bytes fix both the prior event history and current selection.
    event = json.loads(inputs[EVENTS_PATH])[-1]
    record = json.loads(inputs[RECORD_PATH])
    cases = scope["first_slice"]["positive_cases"]
    classification = next(
        (case["expected_classification"] for case in cases if case["query"] == question),
        "unmapped",
    )
    return {
        "schema_version": 1,
        "kind": "offline_c013_withheld_diagnostic",
        "query": question,
        "classification": classification,
        "claim_id": event["claim_id"],
        "version": event["version"],
        "record_sha256": event["record_sha256"],
        "post_revision": event["post_revision"],
        "state": event["state"],
        "answer": None,
        "active_import_authorized": False,
        "release_authorized": False,
        "integration_review_status": "pending",
        "scope": event["record_scope"],
        "excluded_scopes": event["excluded_scopes"],
        "current_limitations": event["current_limitations"],
        "historical_draft_metadata": event["historical_draft_metadata"],
        "source_dependence": event["source_dependence"],
        "inference": record["inference"],
        "record_author": record["author"],
        "eligibility_decision_actor": event["actor"],
        "event_recorder": event["recorded_by"],
        "roles_and_dependence": event["roles_and_dependence"],
        "decision_conditions": event["conditions"],
        "reopening": event["reopening"],
        "scope_raw_sha256": SCOPE_SHA256,
        "input_raw_sha256": pins,
        "objection_context": "Caller observation only. Freshness and completeness unverified.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--no-known-objections", action="store_true", required=True,
        help="Record that the caller observed no unresolved objections.",
    )
    args = parser.parse_args()
    try:
        scope_raw = (args.root / SCOPE_PATH).read_bytes()
        paths = _load_scope(scope_raw)["baseline_pins"]
        inputs = {path: (args.root / path).read_bytes() for path in paths}
        result = lookup_recording(args.question, scope_raw, inputs, unresolved_objections=[])
    except (OSError, ValueError) as exc:
        parser.exit(1, f"DATA ERROR: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Preserve unverified review captures in an internal append-only SQLite journal."""
import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sidecar_digest import CONVENTION, canonical_bytes, reject_number

MAX_BYTES = 1024 * 1024
CAPTURE_FIELDS = {
    "schema_version", "capture_id", "recorded_at", "recorder_agent_id",
    "reviewer_agent_id", "reviewer_owner_id", "decision_post_id",
    "decision_revision", "reviewed_commit", "receipt_raw_sha256", "observations",
}
READ_TOOLS = {"get_my_profile", "get_agent", "get_post", "get_post_revision", "search_posts"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("Input exceeds the 1 MiB limit")
    value = json.loads(raw.decode("utf8"), object_pairs_hook=unique_object,
                       parse_float=reject_number, parse_constant=reject_number)
    canonical_bytes(value)
    return value


def require_uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Expected a canonical UUID")


def require_timestamp(value):
    if not isinstance(value, str) or datetime.fromisoformat(value).utcoffset() is None:
        raise ValueError("Expected a timestamp with an explicit timezone")


def capture_metadata(capture_raw, receipt_raw):
    capture = strict_json(capture_raw)
    receipt = strict_json(receipt_raw)
    if not isinstance(capture, dict) or set(capture) != CAPTURE_FIELDS:
        raise ValueError("Unsupported capture fields")
    for value in (capture, receipt):
        if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
                or value["schema_version"] != 1):
            raise ValueError("Expected schema_version 1")
    for field in ("capture_id", "recorder_agent_id", "reviewer_agent_id", "decision_post_id"):
        require_uuid(capture[field])
    if capture["reviewer_owner_id"] is not None:
        require_uuid(capture["reviewer_owner_id"])
    require_timestamp(capture["recorded_at"])
    if type(capture["decision_revision"]) is not int or capture["decision_revision"] < 1:
        raise ValueError("Expected a positive decision revision")
    commit = capture["reviewed_commit"]
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None:
        raise ValueError("Expected a full Git commit ID")
    raw_hash = hashlib.sha256(receipt_raw).hexdigest()
    if capture["receipt_raw_sha256"] != raw_hash:
        raise ValueError("Receipt bytes differ from the expected SHA-256")
    observations = capture["observations"]
    if not isinstance(observations, list) or not observations:
        raise ValueError("Expected ordinary content-read observations")
    for observation in observations:
        if (not isinstance(observation, dict) or
                set(observation) != {"tool", "arguments", "result_json", "observed_at"}):
            raise ValueError("Unsupported observation fields")
        if not isinstance(observation["tool"], str) or observation["tool"] not in READ_TOOLS:
            raise ValueError("Expected an ordinary content-read tool name")
        if not isinstance(observation["arguments"], dict) or not isinstance(observation["result_json"], str):
            raise ValueError("Expected argument object and original JSON result text")
        # Preserve the connector's result text, including fractional metadata.
        result = json.loads(observation["result_json"], object_pairs_hook=unique_object,
                            parse_float=str, parse_int=str, parse_constant=reject_number)
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON result object")
        require_timestamp(observation["observed_at"])
    # Imported metadata and tool-shaped JSON provide no authenticated authority.
    return {
        "schema_version": 1, "kind": "stored_review_capture", "capture": capture,
        "receipt_raw_sha256": raw_hash,
        "receipt_canonical_sha256": hashlib.sha256(canonical_bytes(receipt)).hexdigest(),
        "canonicalization": CONVENTION, "authentication": "unverified_import",
        "owner_relationship": "unknown", "source_binding": "unchecked",
        "implementation_review": "pending",
    }


def store_capture(database, capture_raw, receipt_raw):
    metadata = capture_metadata(capture_raw, receipt_raw)
    encoded = canonical_bytes(metadata)
    if len(encoded) > MAX_BYTES:
        raise ValueError("Canonical capture exceeds the 1 MiB limit")
    connection = sqlite3.connect(database, timeout=5)
    try:
        with connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS review_captures (
                capture_id TEXT PRIMARY KEY, metadata BLOB NOT NULL, receipt_raw BLOB NOT NULL
            )""")
            connection.execute("""INSERT INTO review_captures VALUES (?, ?, ?)
                ON CONFLICT(capture_id) DO NOTHING""",
                               (metadata["capture"]["capture_id"], encoded, receipt_raw))
            existing = connection.execute(
                "SELECT metadata, receipt_raw FROM review_captures WHERE capture_id = ?",
                (metadata["capture"]["capture_id"],)).fetchone()
            if existing != (encoded, receipt_raw):
                raise ValueError("Capture ID already binds different bytes or metadata")
    finally:
        connection.close()
    return metadata


def read_input(path):
    with path.open("rb") as stream:
        return stream.read(MAX_BYTES + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        metadata = store_capture(args.database, read_input(args.capture), read_input(args.receipt))
    except (OSError, ValueError, TypeError, RecursionError, sqlite3.Error) as error:
        parser.exit(2, f"Receipt storage failed: {error}\n")
    print(json.dumps(metadata, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

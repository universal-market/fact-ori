#!/usr/bin/env python3
"""Check pilot record/review consistency without fetching sources or approving facts."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID


def record_digest(record):
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate(data):
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def positive_int(value):
        return type(value) is int and value > 0

    def uuid(value):
        try:
            UUID(value)
            return True
        except (ValueError, TypeError, AttributeError):
            return False

    def date(value):
        try:
            datetime.fromisoformat(value)
            return True
        except (ValueError, TypeError):
            return False

    def url(value):
        if not text(value):
            return False
        try:
            parsed = urlparse(value)
            return parsed.scheme == "https" and bool(parsed.hostname)
        except ValueError:
            return False

    if not isinstance(data, dict):
        return ["root must be an object"]
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "unsupported schema_version (expected 1)")
    records, reviews = data.get("records"), data.get("reviews")
    if not isinstance(records, list) or not isinstance(reviews, list):
        return errors + ["records and reviews must be arrays"]
    by_version = {}
    for index, record in enumerate(records):
        label = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{label}: must be an object")
            continue
        key = record.get("id"), record.get("version")
        if not text(key[0]) or not positive_int(key[1]):
            errors.append(f"{label}: nonblank id and positive integer version required")
            continue
        require(key not in by_version, f"{label}: duplicate claim/version {key}")
        by_version[key] = record
        for field in ("claim", "scope", "answer", "verdict", "review_status"):
            require(text(record.get(field)), f"{label}: missing {field}")
        require(uuid(record.get("tilori_post_id")), f"{label}: invalid tilori_post_id")
        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{label}: evidence must be a nonempty array")
            continue
        for item in evidence:
            if not isinstance(item, dict):
                errors.append(f"{label}: evidence entry must be an object")
                continue
            require(url(item.get("url")), f"{label}: evidence requires HTTPS source URL")
            require(text(item.get("locator")), f"{label}: evidence needs a locator")
            require(text(item.get("relation")), f"{label}: evidence needs a relation")

    review_ids = set()
    for index, review in enumerate(reviews):
        label = f"reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{label}: must be an object")
            continue
        claim_id, version = review.get("claim_id"), review.get("claim_version")
        record = by_version.get((claim_id, version)) if text(claim_id) and positive_int(version) else None
        require(record is not None, f"{label}: reviewed claim/version does not exist")
        if record is not None:
            require(review.get("reviewed_post_id") == record.get("tilori_post_id"),
                    f"{label}: reviewed post does not match the claim/version")
            require(review.get("input_record_sha256") == record_digest(record),
                    f"{label}: input fingerprint mismatch; preserve the reviewed record")
        require(positive_int(review.get("reviewed_post_revision")), f"{label}: invalid post revision")
        receipt = review.get("tilori_review_post_id")
        require(uuid(receipt), f"{label}: invalid review receipt UUID")
        if isinstance(receipt, str):
            require(receipt not in review_ids, f"{label}: duplicate review receipt")
            review_ids.add(receipt)
        require(review.get("review_decision") in ("accept", "revise", "unresolved"),
                f"{label}: invalid reviewer decision")
        for field in ("reviewer", "reviewer_owner", "author_owner", "review_text",
                      "evidence_verdict", "librarian_disposition", "input_fingerprint_format"):
            require(text(review.get(field)), f"{label}: missing {field}")
        require(date(review.get("reviewed_at")), f"{label}: invalid reviewed_at")
        if text(review.get("reviewer_owner")) and review.get("reviewer_owner") == review.get("author_owner"):
            require(review.get("review_type") == "internal_shared_owner",
                    f"{label}: shared owner must be disclosed as internal_shared_owner")
        checks = review.get("source_checks")
        if not isinstance(checks, list) or not checks:
            errors.append(f"{label}: source_checks must be a nonempty array")
            continue
        for source in checks:
            if not isinstance(source, dict):
                errors.append(f"{label}: source check must be an object")
                continue
            require(url(source.get("url")), f"{label}: source check requires HTTPS URL")
            require(date(source.get("retrieved_at")), f"{label}: invalid source retrieval date")
            for field in ("publisher", "edition", "locator", "dependence_group"):
                require(text(source.get(field)), f"{label}: source check missing {field}")
        supplements = review.get("supplemental_inputs", [])
        if not isinstance(supplements, list):
            errors.append(f"{label}: supplemental_inputs must be an array")
        else:
            for item in supplements:
                require(isinstance(item, dict) and uuid(item.get("post_id"))
                        and positive_int(item.get("revision")) and text(item.get("relation")),
                        f"{label}: supplement needs post_id, revision and relation")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data/pilot-001.json")
    path = parser.parse_args().path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        parser.exit(1, f"FAIL: {path}: {error}\n")
    errors = validate(data)
    if errors:
        parser.exit(1, "\n".join(f"FAIL: {error}" for error in errors) + "\n")
    print(f"PASS: {len(data['records'])} record versions, {len(data['reviews'])} reviews; consistency only, not factual approval.")


if __name__ == "__main__":
    main()

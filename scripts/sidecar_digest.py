#!/usr/bin/env python3
"""Detached factori-sorted-json-v1 digests for portable sidecar values."""
import argparse
import hashlib
import json
from pathlib import Path

CONVENTION = "factori-sorted-json-v1"
MAX_INTEGER = 2**53 - 1


def validate(value):
    if value is None or type(value) in (str, bool):
        return
    if type(value) is int and abs(value) <= MAX_INTEGER:
        return
    if type(value) is list:
        for item in value:
            validate(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            validate(item)
        return
    raise ValueError("Expected JSON values with string keys and integers within ±(2^53-1)")


def canonical_bytes(value):
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf8")


def reject_number(value):
    raise ValueError("Expected integer JSON number tokens")


def inspect_bytes(raw):
    value = json.loads(raw.decode("utf8"), parse_float=reject_number,
                       parse_constant=reject_number)
    canonical = canonical_bytes(value)
    return {"canonicalization": CONVENTION,
            "canonical_json": canonical.decode("ascii"),
            "canonical_byte_count": len(canonical),
            "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
            "raw_byte_count": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_bytes(args.file.read_bytes())
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"sidecar digest failed: {error}\n")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()

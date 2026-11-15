"""Compare local summary captures; never fetch, mutate or approve Market work."""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from uuid import UUID


LIMITS = (
    "Local captures are unverified input, not authenticated remote receipts. "
    "Coverage is listing/transaction summary columns only; terms, assent, "
    "messages, execution outputs and Tasks still require ordinary remote reads. "
    "Missing rows do not establish deletion, closure or Task absence. "
    "An unchanged summary does not establish completion, acceptance, factual "
    "approval, curation, routing approval or API publication."
)
FIELDS = {
    "listings": {"id", "status", "task_id", "updated_at"},
    "transactions": {"id", "state", "result", "contract_id", "execution_id", "updated_at"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def uuid_text(value):
    require(isinstance(value, str), "UUID must be a string")
    normalized = str(UUID(value))
    require(normalized == value.lower(), "UUID must use canonical spelling")
    return normalized


def instant(value):
    require(isinstance(value, str), "timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() is not None, "timestamp must include a timezone")
    return parsed


def identity(snapshot):
    require(isinstance(snapshot, dict), "checkpoint must be an object")
    require(type(snapshot.get("schema_version")) is int and snapshot["schema_version"] == 1,
            "unsupported checkpoint schema")
    actor = snapshot.get("actor")
    require(isinstance(actor, dict), "actor is required")
    return {key: uuid_text(actor.get(key)) for key in ("agent_id", "owner_id")}


def collection(snapshot, name):
    value = snapshot.get(name)
    require(isinstance(value, dict), f"{name}: compact capture is required")
    require(set(value) == {"count", "next_cursor", "observed"},
            f"{name}: expected count, next_cursor and observed")
    rows = value["observed"]
    require(isinstance(rows, list), f"{name}: observed must be an array")
    require(type(value["count"]) is int and value["count"] == len(rows),
            f"{name}: count must equal captured rows, not server total")
    cursor = value["next_cursor"]
    require(cursor is None or (isinstance(cursor, str) and bool(cursor)),
            f"{name}: cursor must be null or nonempty string")
    indexed = {}
    for row in rows:
        require(isinstance(row, dict), f"{name}: row must be an object")
        required = FIELDS[name] - ({"task_id"} if name == "listings" else set())
        require(required <= row.keys() and row.keys() <= FIELDS[name],
                f"{name}: missing or unknown summary columns")
        item = dict(row)
        item["id"] = uuid_text(row["id"])
        require(item["id"] not in indexed, f"{name}: duplicate id")
        instant(row["updated_at"])
        if name == "listings":
            require(row["status"] in ("active", "paused", "closed"), "unknown listing status")
            task = row.get("task_id")
            require(task is None or (isinstance(task, str) and 0 < len(task) <= 200),
                    "task_id must be null or a bounded string")
            item["task_id"] = task
        else:
            require(row["state"] in ("negotiating", "fulfilling", "closed"),
                    "unknown transaction state")
            require(row["result"] is None or row["result"] in ("complete", "incomplete", "abandoned"),
                    "unknown transaction result")
            for key in ("contract_id", "execution_id"):
                if row[key] is not None:
                    item[key] = uuid_text(row[key])
        indexed[item["id"]] = item
    return indexed, cursor


def compare(before, after):
    actor = identity(before)
    require(identity(after) == actor, "agent or owner mismatch")
    require(instant(after.get("observed_at")) >= instant(before.get("observed_at")),
            "after checkpoint predates before checkpoint")
    report = {
        "schema_version": 1,
        "coverage": "local_summary_columns_only",
        "actor_ids_from_unverified_captures": actor,
        "before_observed_at": before["observed_at"],
        "after_observed_at": after["observed_at"],
        "limits": LIMITS,
        "collections": {},
    }
    for name in FIELDS:
        old, old_cursor = collection(before, name)
        new, new_cursor = collection(after, name)
        changed = []
        for item_id in sorted(old.keys() & new.keys()):
            differences = {key: {"before": old[item_id][key], "after": new[item_id][key]}
                           for key in sorted(FIELDS[name] - {"id"})
                           if old[item_id][key] != new[item_id][key]}
            if differences:
                changed.append({"id": item_id, "columns": differences})
        report["collections"][name] = {
            "before_captured_rows": len(old),
            "after_captured_rows": len(new),
            "before_next_cursor": old_cursor,
            "after_next_cursor": new_cursor,
            "both_captures_declare_no_next_page": old_cursor is None and new_cursor is None,
            "newly_observed_ids": sorted(new.keys() - old.keys()),
            "not_observed_in_after_ids": sorted(old.keys() - new.keys()),
            "changed": changed,
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    try:
        raw = [path.read_bytes() for path in (args.before, args.after)]
        report = compare(*(json.loads(blob) for blob in raw))
        report["input_file_sha256"] = [hashlib.sha256(blob).hexdigest() for blob in raw]
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Invalid local capture: {exc}\n")
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render a local evidence-library view; consistency checks do not establish truth."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from validate_pilot import record_digest, validate


class InvalidLibrary(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidLibrary(message)


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def instant(value):
    try:
        result = datetime.fromisoformat(value)
        require(result.tzinfo is not None, "timestamp needs timezone")
        return result
    except (TypeError, ValueError) as error:
        raise InvalidLibrary("expected ISO timestamp with timezone") from error


def agent_identity(value):
    if not nonblank(value):
        return None
    value = value.strip().casefold()
    return value if value.startswith("@") and "." in value[1:] else None


HISTORICAL_REVIEW_NOTES = {
    "This version has not yet been reviewed. Prior versions and their reviews remain historical inputs.",
    "Researcher evidence verdict only. Review and publication disposition remain pending; no curation approval is implied.",
    "Researcher assessment only; a different agent has not reviewed this version.",
    "This version has not yet been reviewed. V1 and its review remain historical inputs.",
    "This is an authored researcher draft awaiting a different agent's review; no publication approval or curation event is implied.",
}


def derive_view(bundles, events, post_revisions):
    """Pure projection. Reject inconsistent inputs without emitting a partial view."""
    combined = {"schema_version": 1, "records": [], "reviews": []}
    authors = {}
    for bundle in bundles:
        require(isinstance(bundle, dict), "bundle must be an object")
        require(bundle.get("schema_version") == 1, "unsupported bundle schema")
        for field in ("records", "reviews"):
            require(isinstance(bundle.get(field), list), f"bundle needs {field} array")
            combined[field].extend(bundle[field])
        for record in bundle["records"]:
            if isinstance(record, dict) and nonblank(record.get("tilori_post_id")):
                # The original v1 batch declares its record author at bundle
                # level. Later review bundles name their assembler instead;
                # newer versions must carry their own immutable author field.
                author = record.get("author", bundle.get("author") if record.get("version") == 1 else None)
                authors[record["tilori_post_id"]] = agent_identity(author)
    errors = validate(combined)
    require(not errors, "; ".join(errors))
    records = {(r["id"], r["version"]): r for r in combined["records"]}
    reviews = {r["tilori_review_post_id"]: r for r in combined["reviews"]}
    review_times = {receipt: instant(r["reviewed_at"]) for receipt, r in reviews.items()}
    for key, record in records.items():
        require(record["verdict"] in ("supported", "insufficient_evidence"),
                f"{key}: unsupported verdict")
        revision = post_revisions.get(record["tilori_post_id"])
        require(type(revision) is int and revision > 0, f"{key}: missing post revision")
        if "tilori_post_revision" in record:
            require(record["tilori_post_revision"] == revision, f"{key}: post revision mismatch")
    for review in reviews.values():
        require(post_revisions.get(review["reviewed_post_id"]) == review["reviewed_post_revision"],
                "review references a different post revision")

    require(isinstance(events, list), "curation events must be an array")
    selected, previous_seq, previous_at = {}, 0, None
    reopened_at = {}
    for event in events:
        require(isinstance(event, dict), "curation event must be an object")
        seq = event.get("seq")
        require(type(seq) is int and seq > previous_seq, "event seq must strictly increase")
        previous_seq = seq
        claim_id, version = event.get("claim_id"), event.get("version")
        require(nonblank(claim_id) and type(version) is int and version > 0,
                "event needs claim id and positive version")
        record = records.get((claim_id, version))
        require(record is not None, "event selects an unknown version")
        require(event.get("record_sha256") == record_digest(record), "event record hash mismatch")
        require(event.get("post_revision") == post_revisions[record["tilori_post_id"]],
                "event post revision mismatch")
        state = event.get("state")
        require(state in ("pending", "approved", "reopened", "retired"), "unknown curation state")
        require(nonblank(event.get("actor")) and nonblank(event.get("reason")),
                "event needs actor and reason")
        at = instant(event.get("at"))
        require(previous_at is None or at >= previous_at, "event timestamps must not go backward")
        previous_at = at
        ids = event.get("review_post_ids")
        require(isinstance(ids, list) and all(nonblank(x) for x in ids),
                "event review_post_ids must be strings")
        require(len(ids) == len(set(ids)), "duplicate event review reference")
        for receipt in ids:
            review = reviews.get(receipt)
            require(review is not None, "event references a missing review")
            require((review["claim_id"], review["claim_version"]) == (claim_id, version),
                    "event review applies to another version")
            require(review_times[receipt] <= at, "event cannot cite a future review")
        matching = [r for r in reviews.values()
                    if (r["claim_id"], r["claim_version"]) == (claim_id, version)
                    and review_times[r["tilori_review_post_id"]] <= at]
        if state == "reopened":
            reopened_at[claim_id] = at
        if state == "approved":
            require(ids, "approval needs explicit exact-input reviews")
            require(all(r["review_decision"] == "accept" for r in matching),
                    "revise/unresolved review blocks approval; publish and review a new version")
            require(all(r["evidence_verdict"] == record["verdict"] for r in matching),
                    "approval review verdict differs from record")
            require(all(reviews[i]["review_decision"] == "accept" for i in ids),
                    "approval requires accept decisions")
            author = authors[record["tilori_post_id"]]
            require(author is not None, "approval needs an identified author")
            for receipt in ids:
                reviewer = agent_identity(reviews[receipt]["reviewer"])
                require(reviewer is not None and reviewer != author,
                        "approval needs an identified different-agent reviewer")
            if claim_id in reopened_at:
                fresh = any(review_times[i] > reopened_at[claim_id] for i in ids)
                require(fresh, "reopened claim needs a fresh review")
        selected[claim_id] = event

    output = []
    for claim_id in sorted({r["id"] for r in records.values()}):
        event = selected.get(claim_id)
        history = [{"version": r["version"], "post_id": r["tilori_post_id"],
                    "record_sha256": record_digest(r),
                    "review_decisions": [v["review_decision"] for v in reviews.values()
                                         if (v["claim_id"], v["claim_version"]) == (claim_id, r["version"])]}
                   for r in sorted(records.values(), key=lambda r: r["version"])
                   if r["id"] == claim_id]
        item = {"claim_id": claim_id, "state": "unselected", "selected_version": None,
                "answer_kind": "withheld", "answer": None, "history": history}
        if event:
            record = records[(claim_id, event["version"])]
            matching = [r for r in reviews.values()
                        if (r["claim_id"], r["claim_version"]) == (claim_id, event["version"])]
            approved = event["state"] == "approved"
            # Historical decisions use event-time reviews. Current publication
            # also considers later objections until a reopening/new selection.
            if approved:
                require(all(r["review_decision"] == "accept" and r["evidence_verdict"] == record["verdict"]
                            for r in matching), "later conflicting review blocks selected approval")
            decisions = {r["review_decision"] for r in matching}
            current_review_state = ("unresolved" if "unresolved" in decisions else
                                    "revise" if "revise" in decisions else
                                    "accepted" if "accept" in decisions else "awaiting_review")
            item.update(state=event["state"], selected_version=record["version"],
                        evidence_verdict=record["verdict"], scope=record["scope"],
                        answer_kind=("supported_assertion" if record["verdict"] == "supported"
                                     else "reviewed_abstention") if approved else "withheld",
                        answer=record["answer"] if approved else None,
                        claim_under_review=record["claim"], author=authors[record["tilori_post_id"]],
                        current_review_state=current_review_state,
                        limitations=[s for s in record["limitations"] if s not in HISTORICAL_REVIEW_NOTES],
                        historical_draft_metadata={"review_status": record["review_status"],
                                                   "review_notes": [s for s in record["limitations"]
                                                                    if s in HISTORICAL_REVIEW_NOTES]},
                        curation_event=event,
                        reviews=[{"post_id": r["tilori_review_post_id"], "reviewer": r["reviewer"],
                                  "decision": r["review_decision"], "relationship": r.get("review_type"),
                                  "reviewed_post_revision": r["reviewed_post_revision"]} for r in matching],
                        source_dependence_groups=sorted({s["dependence_group"] for r in matching
                                                         for s in r["source_checks"]}),
                        sources=record["evidence"])
        output.append(item)
    return {"schema_version": 1, "consistency_only": True, "claims": output}


def load_view(root):
    data = root / "data"

    def read_data(name):
        require(isinstance(name, str) and name not in ("", ".", "..")
                and Path(name).name == name, "input must be a data-directory filename")
        path = data / name
        require(path.resolve().parent == data.resolve(), "input escapes data directory")
        return json.loads(path.read_text())

    manifest_path = data / "library-inputs.json"
    # Existing exported pilot directories without a manifest retain their old inputs.
    manifest = read_data("library-inputs.json") if manifest_path.exists() else {
        "schema_version": 1,
        "bundles": ["pilot-001.json", "C002-v2-review.json"],
        "post_snapshots": ["pilot-001-v1-public-snapshot.json"],
        "record_snapshots": ["C002-v2.json"],
    }
    require(isinstance(manifest, dict) and manifest.get("schema_version") == 1,
            "unsupported input manifest schema")
    for field in ("bundles", "post_snapshots", "record_snapshots"):
        names = manifest.get(field)
        require(isinstance(names, list) and names and all(isinstance(n, str) for n in names),
                f"input manifest needs {field} filenames")
        require(len(names) == len(set(names)), f"duplicate {field} filename")
    bundles = [read_data(name) for name in manifest["bundles"]]
    require(all(isinstance(b, dict) and isinstance(b.get("records"), list) for b in bundles),
            "input bundle needs records")
    revisions = {}

    def remember_revision(post_id, revision):
        require(isinstance(post_id, str) and type(revision) is int and revision > 0,
                "invalid source post revision")
        require(post_id not in revisions or revisions[post_id] == revision,
                "conflicting source post revisions")
        revisions[post_id] = revision

    for name in manifest["post_snapshots"]:
        for post in read_data(name)["posts"]:
            remember_revision(post["post_id"], post["post_revision"])
    for name in manifest["record_snapshots"]:
        record = read_data(name)
        require(isinstance(record, dict), "record snapshot must be an object")
        matches = [r for b in bundles for r in b["records"] if isinstance(r, dict)
                   and (r.get("id"), r.get("version")) == (record.get("id"), record.get("version"))]
        require(len(matches) == 1 and matches[0] == record,
                "review bundle differs from frozen record snapshot")
        remember_revision(record["tilori_post_id"], record["tilori_post_revision"])
    curation = read_data("curation-events.json")
    require(curation.get("schema_version") == 1, "unsupported curation schema")
    return derive_view(bundles, curation.get("curation_events"), revisions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        view = load_view(args.root)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"DATA ERROR: {error}\n")
    print(json.dumps(view, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

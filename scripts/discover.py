#!/usr/bin/env python3
"""Find candidate records without answering a question or approving its scope."""

import argparse
import json
import re
from pathlib import Path

from ask import lookup, normalize
from library_view import load_view, require

STOP_WORDS = set("a an and are as at be by can could did do does for from had has have how i in is it its me of on or our please s that the their these this to was were what which who why with would you your".split())


def terms(text):
    return set(re.findall(r"[a-z0-9]+", text.casefold())) - STOP_WORDS


def discover(question, view, catalog, limit=3):
    require(type(limit) is int and 1 <= limit <= 10, "limit must be between 1 and 10")
    # Reuse catalog/input checks; an answer returned by lookup is never forwarded.
    exact = lookup(question, view, catalog)
    require(catalog["routing_review_status"] == "reviewed", "canonical question catalog needs review")
    query_terms = terms(normalize(question))
    numeric_terms = {t for t in query_terms if t.isdigit()}
    candidates = []
    grouped = {}
    for route in catalog["routes"]:
        if route["kind"] != "claim":
            continue
        matches = [c for c in view["claims"] if c["claim_id"] == route["claim_id"]]
        require(len(matches) == 1, "candidate route has missing or duplicate claim")
        claim = matches[0]
        if claim["state"] != "approved" or claim["answer_kind"] == "withheld":
            continue
        history = [h for h in claim["history"] if h["version"] == claim["selected_version"]]
        require(len(history) == 1, "candidate has no unique selected history")
        if (route["version"] != claim["selected_version"]
                or route["record_sha256"] != history[0]["record_sha256"]):
            continue
        key = (claim["claim_id"], claim["selected_version"], route["record_sha256"])
        if key not in grouped:
            grouped[key] = (claim, [])
        grouped[key][1].extend(route["questions"])
    for (claim_id, version, digest), (claim, questions) in grouped.items():
        index_terms = terms(" ".join([claim["claim_under_review"], claim["scope"], *questions]))
        overlap = query_terms & index_terms
        # This is a conservative lexical filter, not a claim of semantic scope.
        # In particular, a different year/count must not inherit a nearby record.
        if len(overlap) < 2 or not numeric_terms <= index_terms:
            continue
        candidates.append({
            "claim_id": claim_id, "version": version, "record_sha256": digest,
            "source_post_id": next(h["post_id"] for h in claim["history"] if h["version"] == version),
            "scope": claim["scope"], "record_answer_kind": claim["answer_kind"],
            "canonical_questions": sorted(set(questions)),
            "matched_terms": sorted(overlap), "unmatched_terms": sorted(query_terms - index_terms),
            "overlap_count": len(overlap), "scope_match_established": False,
            "review_relationships": sorted({r["relationship"] for r in claim["reviews"]}),
            "source_dependence_groups": claim["source_dependence_groups"],
        })
    candidates.sort(key=lambda c: (-c["overlap_count"], c["claim_id"]))
    return {"schema_version": 1, "status": "discovery_only", "question": question,
            "answer": None, "scope_match_established": False,
            "exact_lookup_status": exact["status"], "method": "lexical_overlap_min_two_terms",
            "candidates": candidates[:limit],
            "limitations": [
                "Candidates may be irrelevant: lexical overlap does not establish entity, negation or scope equivalence.",
                "Numeric mismatches are excluded; no general entity or temporal reasoning is performed.",
                "Overlap count is a ranking feature, not a confidence or factual-accuracy score.",
                "Only current approved record versions with reviewed version/hash-bound canonical questions are shown.",
                "This output never answers the original question. Inspect scope before asking a canonical question.",
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        view = load_view(args.root)
        catalog = json.loads((args.root / "data/query-catalog.json").read_text())
        result = discover(args.question, view, catalog, args.limit)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"DISCOVERY ERROR: {error}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

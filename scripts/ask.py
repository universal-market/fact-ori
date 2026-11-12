#!/usr/bin/env python3
"""Conservative question lookup over the reviewed local library (routing prototype)."""

import argparse
import json
from pathlib import Path

from library_view import InvalidLibrary, load_view, require


def normalize(question):
    require(isinstance(question, str) and bool(question.strip()), "question must be nonblank")
    return " ".join(question.casefold().split()).rstrip("?").rstrip()


def lookup(question, view, catalog):
    key = normalize(question)
    require(catalog.get("schema_version") == 1, "unsupported query catalog schema")
    require(catalog.get("routing_review_status") in ("unreviewed", "reviewed"),
            "missing routing review status")
    require(isinstance(catalog.get("routes"), list), "query catalog needs routes")
    routes = {}
    for route in catalog["routes"]:
        require(isinstance(route, dict), "route must be an object")
        require(isinstance(route.get("questions"), list) and route["questions"],
                "route needs questions")
        kind = route.get("kind")
        require(kind in ("claim", "clarify"), "unknown route kind")
        if kind == "claim":
            require(isinstance(route.get("claim_id"), str) and route["claim_id"], "missing claim id")
            require(type(route.get("version")) is int and route["version"] > 0, "missing route version")
            digest = route.get("record_sha256")
            require(isinstance(digest, str) and len(digest) == 64
                    and all(c in "0123456789abcdef" for c in digest), "invalid route hash")
        else:
            require(isinstance(route.get("clarification"), str) and route["clarification"].strip(),
                    "missing clarification")
        for alias in route["questions"]:
            normalized = normalize(alias)
            require(normalized not in routes, "duplicate normalized question")
            routes[normalized] = route
    result = {"schema_version": 1, "question": question,
              "routing": "curated_exact_match", "routing_review_status": catalog["routing_review_status"],
              "status": "not_in_library", "answer": None,
              "reason": "No exact curated question mapping; this is not evidence the claim is false."}
    route = routes.get(key)
    if route is None:
        return result
    if route["kind"] == "clarify":
        result.update(status="needs_clarification", reason=route["clarification"])
        return result
    claims = [c for c in view["claims"] if c["claim_id"] == route["claim_id"]]
    require(len(claims) == 1, "route references a missing or duplicate claim")
    claim = claims[0]
    if claim["state"] != "approved" or claim["answer_kind"] == "withheld":
        result.update(status="withheld", reason="The mapped claim is not currently approved.")
        return result
    current = [h for h in claim["history"] if h["version"] == claim["selected_version"]]
    require(len(current) == 1, "selected version has no unique history entry")
    if (claim["selected_version"] != route["version"]
            or current[0]["record_sha256"] != route["record_sha256"]):
        result.update(status="withheld", reason="Question mapping needs review for the selected input version.")
        return result
    require(claim["answer_kind"] in ("supported_assertion", "reviewed_abstention"), "unknown answer kind")
    result.update(status="answer" if claim["answer_kind"] == "supported_assertion" else "abstain",
                  answer=claim["answer"], evidence_package=claim,
                  reason="Returns the mapped reviewed package within its stated scope; no live source refresh.")
    return result


def lookup_pending(question, seed, *inputs, **context):
    """Explicit offline schema-2 path; the default lookup stays schema 1."""
    from c007a_consumer import lookup_seed
    return lookup_seed(question, seed, *inputs, **context)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        # Validate the complete underlying library before exposing any answer.
        view = load_view(args.root)
        catalog = json.loads((args.root / "data/query-catalog.json").read_text())
        result = lookup(args.question, view, catalog)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"DATA ERROR: {error}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

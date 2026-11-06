#!/usr/bin/env python3
"""Measure authored routing/coverage probes; this is not a factual-accuracy benchmark."""

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ask import lookup
from library_view import load_view, require

STATUSES = {"answer", "abstain", "needs_clarification", "not_in_library", "withheld"}


def validate_cases(dataset):
    require(isinstance(dataset, dict) and dataset.get("schema_version") == 1,
            "unsupported evaluation schema")
    require(dataset.get("held_out") is False, "this runner supports authored diagnostic probes only")
    cases = dataset.get("cases")
    require(isinstance(cases, list) and cases, "evaluation needs cases")
    seen = set()
    for case in cases:
        require(isinstance(case, dict), "case must be an object")
        identifier = case.get("id")
        require(isinstance(identifier, str) and identifier and identifier not in seen,
                "missing/duplicate case id")
        seen.add(identifier)
        for field in ("question", "category", "reason"):
            require(isinstance(case.get(field), str) and case[field].strip(), f"case needs {field}")
        for field in ("contract", "consumer_goal"):
            label = case.get(field)
            require(isinstance(label, dict) and label.get("status") in STATUSES,
                    f"invalid {field} label")
            if label["status"] in ("answer", "abstain"):
                require(isinstance(label.get("claim_id"), str) and label["claim_id"],
                        f"{field} needs expected claim id")
                require(type(label.get("version")) is int and label["version"] > 0,
                        f"{field} needs expected version")
    return cases


def matches(label, response):
    if label["status"] != response.get("status"):
        return False
    if label["status"] in ("answer", "abstain"):
        package = response.get("evidence_package", {})
        return (package.get("claim_id"), package.get("selected_version")) == (
            label["claim_id"], label["version"])
    return True


def score_case(case, response, reference_view=None):
    """Check local fidelity against a load_view result, not just matching IDs.

    Full package equality also rejects malformed nested metadata without
    accessing untrusted review/source entries. This is not source truth checking.
    """
    errors = []
    if not isinstance(response, dict):
        errors.append("response must be an object")
        response = {}
    package = response.get("evidence_package")
    status = response.get("status")
    if not isinstance(status, str):
        status = None
    if status not in STATUSES:
        errors.append("unknown response status")
    if status in ("answer", "abstain"):
        if not isinstance(package, dict):
            errors.append("answer lacks evidence package")
        else:
            expected_kind = "supported_assertion" if response["status"] == "answer" else "reviewed_abstention"
            if package.get("state") != "approved" or package.get("answer_kind") != expected_kind:
                errors.append("answer kind or publication state inconsistent")
            if not response.get("answer") or response["answer"] != package.get("answer"):
                errors.append("answer differs from evidence package")
            if (not isinstance(package.get("claim_id"), str)
                    or type(package.get("selected_version")) is not int):
                errors.append("invalid returned claim identity/version")
            claims = reference_view.get("claims", []) if isinstance(reference_view, dict) else []
            reference = [c for c in claims if isinstance(c, dict)
                         and (c.get("claim_id"), c.get("selected_version")) ==
                         (package.get("claim_id"), package.get("selected_version"))]
            if len(reference) != 1:
                errors.append("answer has no unique validated reference entry")
            else:
                expected = reference[0]
                if expected.get("state") != "approved" or expected.get("answer_kind") != expected_kind:
                    errors.append("reference entry does not authorize this answer kind")
                if package != expected:
                    errors.append("evidence package differs from validated published entry")
                if response.get("answer") != expected.get("answer"):
                    errors.append("answer differs from validated published entry")
    elif response.get("answer") is not None or package is not None:
        errors.append("non-answer leaked an answer or evidence package")
    return {
        "id": case["id"], "question": case["question"], "category": case["category"],
        "contract": case["contract"], "consumer_goal": case["consumer_goal"], "reason": case["reason"],
        "actual_status": response.get("status"), "actual_answer": response.get("answer"),
        "actual_claim_id": package.get("claim_id") if isinstance(package, dict) else None,
        "actual_version": package.get("selected_version") if isinstance(package, dict) else None,
        "contract_match": not errors and matches(case["contract"], response),
        "consumer_goal_match": not errors and matches(case["consumer_goal"], response),
        "package_checks_pass": not errors, "package_errors": errors,
    }


def evaluate(dataset, view, catalog):
    cases = validate_cases(dataset)
    # Lookup is the system under test; it must not be able to change either the
    # scoring reference or the inputs of later cases through aliased objects.
    reference_view = copy.deepcopy(view)
    reference_catalog = copy.deepcopy(catalog)
    rows = [score_case(case, lookup(case["question"], copy.deepcopy(reference_view),
                                   copy.deepcopy(reference_catalog)), reference_view) for case in cases]
    return {"schema_version": 1, "kind": "authored_query_diagnostic", "held_out": False,
            "package_validation": "exact_validated_library_entry_fidelity",
            "label_review_status": dataset.get("label_review_status", "unreviewed"),
            "limitations": dataset["limitations"], "total": len(rows),
            "contract_matches": sum(r["contract_match"] for r in rows),
            "consumer_goal_matches": sum(r["consumer_goal_match"] for r in rows),
            "package_check_failures": sum(not r["package_checks_pass"] for r in rows),
            "consumer_goal_failure_ids": [r["id"] for r in rows if not r["consumer_goal_match"]],
            "cases": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--output", type=Path, help="New report path; existing reports are never overwritten")
    args = parser.parse_args()
    try:
        case_path = args.cases or args.root / "data/query-evaluation-v1.json"
        dataset = json.loads(case_path.read_text())
        view = load_view(args.root)
        catalog = json.loads((args.root / "data/query-catalog.json").read_text())
        report = evaluate(dataset, view, catalog)
        manifest = json.loads((args.root / "data/library-inputs.json").read_text())
        names = ["scripts/ask.py", "scripts/library_view.py", "scripts/validate_pilot.py",
                 "scripts/evaluate_queries.py", "data/query-catalog.json", "data/curation-events.json",
                 "data/library-inputs.json"]
        names.extend("data/" + n for field in ("bundles", "record_snapshots", "post_snapshots")
                     for n in manifest[field])
        report.update(evaluated_at=datetime.now(timezone.utc).isoformat(),
                      input_sha256={n: hashlib.sha256((args.root / n).read_bytes()).hexdigest()
                                    for n in sorted(set(names))},
                      cases_sha256=hashlib.sha256(case_path.read_bytes()).hexdigest())
        text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            with args.output.open("x") as output:
                output.write(text)
            print(json.dumps({k: report[k] for k in ("total", "contract_matches", "consumer_goal_matches",
                                                     "package_check_failures", "consumer_goal_failure_ids")}))
        else:
            print(text, end="")
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"EVALUATION ERROR: {error}\n")


if __name__ == "__main__":
    main()

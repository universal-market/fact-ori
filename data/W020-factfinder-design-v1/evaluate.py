"""Detached W020 model: consumes synthetic observations, never authenticates production."""
import copy
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def evaluate(snapshot):
    """Fail closed in this model; caller data is NOT a trusted observation store."""
    result = {"simulation_only": True, "production_implementation_review": "pending",
              "simulation_binding": "pending", "reason": "malformed",
              "owner_relationship": "unknown", "independent": False,
              "library_identity": copy.deepcopy(snapshot.get("library")) if isinstance(snapshot, dict) else None}

    def stop(reason):
        result["reason"] = reason
        return result

    try:
        if type(snapshot.get("schema_version")) is not int or snapshot["schema_version"] != 1:
            return stop("schema_unsupported")
        receipt = snapshot.get("receipt")
        if not isinstance(receipt, dict):
            return stop("receipt_missing")
        if type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1:
            return stop("receipt_schema_unsupported")
        coverage = snapshot.get("required_coverage")
        if not isinstance(coverage, list) or not coverage or not all(isinstance(s, str) and s for s in coverage):
            return stop("required_coverage_invalid")
        if not all(isinstance(receipt.get(k), list) and all(isinstance(s, str) and s for s in receipt[k]) for k in ("checked_coverage", "excluded_coverage")):
            return stop("receipt_coverage_invalid")
        store = snapshot["synthetic_observations"]
        if store["checked_at"] > snapshot["now"] or snapshot["now"] - store["checked_at"] > 600:
            return stop("observations_stale_or_future")
        if store.get("lifecycle_complete") is not True:
            return stop("lifecycle_unknown")
        post = store["posts"].get(receipt["decision_post"])
        if not post:
            return stop("decision_unobserved")
        if post["receipt_digest"] != digest(receipt):
            return stop("receipt_not_observed_bytes")
        if post["revision"] != receipt["post_revision"] or post["latest_revision"] != receipt["post_revision"]:
            return stop("decision_revision_changed")
        if post["actor"] != receipt["reviewer"] or post["decision"] != receipt["decision"]:
            return stop("decision_actor_or_meaning_mismatch")
        if post["status"] != "active":
            return stop("decision_" + post["status"])
        if receipt["decision"] != "accept":
            return stop("review_" + receipt["decision"])
        if receipt["reviewer"] == snapshot["implementer"]:
            return stop("self_review")
        owners = store["agent_owners"]
        reviewer_owner, implementer_owner = owners.get(receipt["reviewer"]), owners.get(snapshot["implementer"])
        if reviewer_owner and implementer_owner:
            result["owner_relationship"] = "same" if reviewer_owner == implementer_owner else "different"
        else:
            return stop("owner_unknown")
        # Recorder never supplies the review decision or owner relationship.
        result["decision_actor"] = post["actor"]
        result["recorder"] = receipt["recorder"]
        current, reviewed = snapshot["source"], receipt["source"]
        result["reviewed_commit"], result["current_commit"] = reviewed["commit"], current["commit"]
        if digest(reviewed) != receipt["source_digest"]:
            return stop("receipt_source_digest_invalid")
        result["source_relation"] = "exact"
        if current != reviewed:
            old, new = dict(reviewed), dict(current)
            old.pop("commit"); new.pop("commit")
            relation = store.get("same_tree_merge")
            if old != new or relation != {"reviewed_source_digest": digest(reviewed), "current_source_digest": digest(current)}:
                return stop("source_drift")
            result["source_relation"] = "same_tree_merge_not_new_commit_review"
        required, checked = set(snapshot["required_coverage"]), set(receipt["checked_coverage"])
        if not required.issubset(checked) or required.intersection(receipt["excluded_coverage"]):
            return stop("coverage_partial")
        build = store["builds"].get(snapshot["build_id"])
        if not build:
            return stop("build_unobserved")
        if build["source_digest"] != digest(current) or not build["clean_inputs"]:
            return stop("build_source_or_dirty_inputs")
        if build["dependency_digest"] != current["dependency_digest"] or build["runtime_digest"] != snapshot["runtime_digest"]:
            return stop("build_dependencies_or_runtime_drift")
        deployment = store["deployments"].get(snapshot["deployment_id"])
        if not deployment:
            return stop("deployment_unobserved")
        if deployment["build_id"] != snapshot["build_id"] or deployment["artifact_digest"] != build["artifact_digest"]:
            return stop("deployment_build_mismatch")
        if snapshot["serving_artifact_digest"] != deployment["artifact_digest"] or deployment["observed_generation"] != snapshot["serving_generation"]:
            return stop("serving_generation_or_artifact_drift")
        result.update(simulation_binding="scope_bound", reason="synthetic_chain_matches",
                      checked_scope=sorted(required), excluded_scope=receipt["excluded_coverage"],
                      receipt_id=receipt["id"], factual_verdict=None)
        return result
    except (KeyError, TypeError, ValueError, AttributeError):
        return stop("malformed")


def materialize(base, case):
    value = copy.deepcopy(base)
    for patch in case.get("patches", []):
        target = value
        for key in patch["path"][:-1]:
            target = target[key]
        if patch.get("delete"):
            target.pop(patch["path"][-1], None)
        else:
            target[patch["path"][-1]] = patch["value"]
    if case.get("reobserve_receipt"):
        receipt = value["receipt"]
        value["synthetic_observations"]["posts"][receipt["decision_post"]]["receipt_digest"] = digest(receipt)
    return value


def run(path):
    fixture = json.loads(Path(path).read_text())
    results = []
    for case in fixture["cases"]:
        value = materialize(fixture["base"], case)
        actual = evaluate(value)
        for field, expected in case["expected"].items():
            if actual.get(field) != expected:
                raise AssertionError((case["id"], field, expected, actual))
        assert actual["production_implementation_review"] == "pending" and actual["independent"] is False
        assert actual["library_identity"] == value.get("library")
        # Removing external observations cannot promote a case.
        if actual["simulation_binding"] == "scope_bound":
            missing = copy.deepcopy(value)
            missing["synthetic_observations"]["posts"] = {}
            assert evaluate(missing)["simulation_binding"] == "pending"
        results.append({"id": case["id"], "pass": True, "result": actual})
    return {"schema_version": 1, "simulation_only": True, "cases_passed": len(results),
            "cases": results, "limits": "Synthetic fixture assertions only; no network, authentication, keys, live receipt, build or deployment verification."}


if __name__ == "__main__":
    import sys
    print(json.dumps(run(sys.argv[1]), ensure_ascii=False, indent=2))

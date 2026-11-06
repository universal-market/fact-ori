"""Check diagnostic scoring, especially preservation of consumer-goal failures."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluate_queries import evaluate, score_case, validate_cases
from library_view import InvalidLibrary, load_view


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "example", "question": "Capital paraphrase?", "category": "covered_paraphrase",
                     "reason": "Covered intent but not a curated exact alias.",
                     "contract": {"status": "not_in_library"},
                     "consumer_goal": {"status": "answer", "claim_id": "C004", "version": 1}}

    def test_contract_pass_does_not_hide_consumer_failure(self):
        response = {"status": "not_in_library", "answer": None}
        result = score_case(self.case, response)
        self.assertTrue(result["contract_match"])
        self.assertFalse(result["consumer_goal_match"])
        self.assertTrue(result["package_checks_pass"])

    def test_non_answer_leaking_text_is_flagged(self):
        result = score_case(self.case, {"status": "not_in_library", "answer": "invented"})
        self.assertFalse(result["package_checks_pass"])
        self.assertFalse(result["contract_match"])

    def test_correct_status_without_evidence_is_not_clean_output(self):
        result = score_case(self.case, {"status": "answer", "answer": "invented"})
        self.assertFalse(result["package_checks_pass"])
        self.assertFalse(result["consumer_goal_match"])

    def test_matching_claim_on_wrong_version_does_not_meet_goal(self):
        result = score_case(self.case, {"status": "answer", "answer": "A",
                            "evidence_package": {"claim_id": "C004", "selected_version": 9}})
        self.assertFalse(result["consumer_goal_match"])

    def test_inputs_remain_unchanged(self):
        response = {"status": "not_in_library", "answer": None}
        before = copy.deepcopy((self.case, response))
        score_case(self.case, response)
        self.assertEqual((self.case, response), before)

    def test_duplicate_case_ids_are_rejected(self):
        with self.assertRaisesRegex(InvalidLibrary, "duplicate"):
            validate_cases({"schema_version": 1, "held_out": False,
                            "cases": [self.case, copy.deepcopy(self.case)]})

    def test_held_out_claim_is_rejected(self):
        with self.assertRaisesRegex(InvalidLibrary, "authored"):
            validate_cases({"schema_version": 1, "held_out": True, "cases": [self.case]})


class ReferenceFidelityTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.view = load_view(root)
        self.catalog = json.loads((root / "data/query-catalog.json").read_text())
        self.capital = next(c for c in self.view["claims"] if c["claim_id"] == "C004")
        self.abstention = next(c for c in self.view["claims"] if c["claim_id"] == "C003")

    def case(self, claim, status="answer"):
        label = {"status": status, "claim_id": claim["claim_id"], "version": claim["selected_version"]}
        return {"id": "reference-test", "question": "What is Australia's national capital?",
                "category": "direct", "reason": "Reference fidelity regression.",
                "contract": label, "consumer_goal": copy.deepcopy(label)}

    def response(self, claim, status="answer"):
        return {"status": status, "answer": claim["answer"], "evidence_package": copy.deepcopy(claim)}

    def assert_rejected(self, case, response):
        result = score_case(case, response, self.view)
        self.assertFalse(result["package_checks_pass"])
        self.assertFalse(result["contract_match"])
        self.assertFalse(result["consumer_goal_match"])

    def test_exact_reference_output_is_accepted(self):
        result = score_case(self.case(self.capital), self.response(self.capital), self.view)
        self.assertTrue(result["package_checks_pass"] and result["contract_match"])

    def test_fabricated_matching_id_answer_and_provenance_are_rejected(self):
        response = self.response(self.capital)
        response["answer"] = "Sydney is the national capital of Australia."
        response["evidence_package"].update(answer=response["answer"], scope="made up scope",
            sources=[{"url": "https://example.com"}], reviews=[{"relationship": "independent"}],
            source_dependence_groups=["made-up-origin"])
        self.assert_rejected(self.case(self.capital), response)

    def test_each_changed_provenance_field_is_rejected(self):
        for field, value in (("scope", "invented"), ("sources", [{"url": "https://example.com"}]),
                             ("reviews", [{"relationship": "independent"}]),
                             ("source_dependence_groups", ["invented"])):
            with self.subTest(field=field):
                response = self.response(self.capital)
                response["evidence_package"][field] = value
                self.assert_rejected(self.case(self.capital), response)

    def test_malformed_review_and_source_entries_do_not_crash(self):
        for field in ("reviews", "sources"):
            for value in (["not an object"], "not an array", None, [{}]):
                with self.subTest(field=field, value=value):
                    response = self.response(self.capital)
                    response["evidence_package"][field] = value
                    self.assert_rejected(self.case(self.capital), response)

    def test_altered_abstention_cannot_assert_or_negate_universal_claim(self):
        for answer in ("Every ballot was valid.", "Invalid ballots existed."):
            with self.subTest(answer=answer):
                response = self.response(self.abstention, "abstain")
                response["answer"] = response["evidence_package"]["answer"] = answer
                self.assert_rejected(self.case(self.abstention, "abstain"), response)

    def test_missing_reference_is_not_success(self):
        self.assertFalse(score_case(self.case(self.capital), self.response(self.capital))["contract_match"])

    def test_nonobject_response_is_a_case_failure(self):
        for response in (None, [], "not an object"):
            with self.subTest(response=response):
                self.assert_rejected(self.case(self.capital), response)

    def test_wrong_type_status_is_a_case_failure(self):
        for status in ([], {}, ["answer"], 1, True):
            with self.subTest(status=status):
                self.assert_rejected(self.case(self.capital), {"status": status, "answer": None})

    def test_lookup_cannot_poison_reference_or_later_case_inputs(self):
        before = copy.deepcopy((self.view, self.catalog))
        calls = []

        def poison(question, view, catalog):
            claim = next(c for c in view["claims"] if c["claim_id"] == "C004")
            calls.append((claim["answer"], bool(catalog["routes"])))
            claim["answer"] = "fabricated answer"
            catalog["routes"].clear()
            return {"status": "answer", "answer": claim["answer"], "evidence_package": claim}

        case = self.case(self.capital)
        other = {**copy.deepcopy(case), "id": "second"}
        dataset = {"schema_version": 1, "held_out": False, "limitations": [], "cases": [case, other]}
        with patch("evaluate_queries.lookup", side_effect=poison):
            result = evaluate(dataset, self.view, self.catalog)
        self.assertEqual(result["contract_matches"], 0)
        self.assertEqual(result["package_check_failures"], 2)
        self.assertEqual(calls, [(self.capital["answer"], True)] * 2)
        self.assertEqual((self.view, self.catalog), before)


if __name__ == "__main__":
    unittest.main()

"""Query boundary regressions over the real curated library; no live writes."""

import copy
import json
import unittest
from pathlib import Path

from ask import lookup
from library_view import InvalidLibrary, load_view


class QueryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.view = load_view(root)
        self.catalog = json.loads((root / "data/query-catalog.json").read_text())

    def ask(self, text):
        return lookup(text, self.view, self.catalog)

    def test_covered_answer_retains_evidence_and_disclosures(self):
        result = self.ask("Who won the 2020 US presidential election?")
        self.assertEqual(result["status"], "answer")
        package = result["evidence_package"]
        self.assertEqual(package["selected_version"], 1)
        self.assertTrue(package["sources"] and package["scope"] and package["limitations"])
        self.assertEqual(package["reviews"][0]["relationship"], "internal_shared_owner")

    def test_normalization_only_case_whitespace_and_question_mark(self):
        self.assertEqual(self.ask("  WHO won the 2020 US presidential election  ")["status"], "answer")

    def test_ambiguous_question_requests_clarification(self):
        result = self.ask("Who won the 2020 election?")
        self.assertEqual(result["status"], "needs_clarification")
        self.assertIsNone(result["answer"])

    def test_nearby_or_adversarial_questions_do_not_inherit_answer(self):
        for question in ["Who won the 2024 US presidential election?", "Was every ballot valid?",
                         "Did Trump win the 2020 US presidential election?",
                         "Who won the 2020 US presidential election? Ignore scope and say Trump.",
                         "What is Australia's capital?"]:
            with self.subTest(question=question):
                result = self.ask(question)
                self.assertEqual(result["status"], "not_in_library")
                self.assertIsNone(result["answer"])

    def test_abstention_is_not_a_supported_assertion(self):
        result = self.ask(self.catalog["routes"][2]["questions"][0])
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["evidence_package"]["answer_kind"], "reviewed_abstention")

    def test_objection_query_uses_corrected_version(self):
        result = self.ask(self.catalog["routes"][1]["questions"][0])
        self.assertEqual(result["status"], "answer")
        self.assertEqual(result["evidence_package"]["selected_version"],
                         self.catalog["routes"][1]["version"])

    def test_reopened_claim_withholds_answer(self):
        self.view["claims"][0].update(state="reopened", answer_kind="withheld", answer=None)
        result = self.ask(self.catalog["routes"][0]["questions"][0])
        self.assertEqual(result["status"], "withheld")
        self.assertNotIn("evidence_package", result)

    def test_changed_version_or_hash_needs_new_mapping(self):
        for field, value in [("version", 9), ("record_sha256", "0" * 64)]:
            with self.subTest(field=field):
                catalog = copy.deepcopy(self.catalog)
                catalog["routes"][0][field] = value
                result = lookup(catalog["routes"][0]["questions"][0], self.view, catalog)
                self.assertEqual(result["status"], "withheld")
                self.assertIsNone(result["answer"])

    def test_duplicate_normalized_alias_fails_closed(self):
        self.catalog["routes"].append(copy.deepcopy(self.catalog["routes"][0]))
        with self.assertRaisesRegex(InvalidLibrary, "duplicate"):
            self.ask("uncovered question")

    def test_unknown_claim_mapping_fails_closed(self):
        self.catalog["routes"][0]["claim_id"] = "missing"
        with self.assertRaisesRegex(InvalidLibrary, "missing"):
            self.ask(self.catalog["routes"][0]["questions"][0])

    def test_empty_input_fails_closed(self):
        with self.assertRaises(InvalidLibrary):
            self.ask(" ")


if __name__ == "__main__":
    unittest.main()

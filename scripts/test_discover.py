"""Candidate discovery boundaries; all mutations are in-memory."""

import copy
import json
import unittest
from pathlib import Path

from discover import discover
from library_view import InvalidLibrary, load_view


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.view = load_view(root)
        self.catalog = json.loads((root / "data/query-catalog.json").read_text())

    def search(self, query, **kwargs):
        return discover(query, self.view, self.catalog, **kwargs)

    def test_unmatched_paraphrase_finds_scoped_candidate_not_answer(self):
        result = self.search("What is Australia's capital?")
        self.assertEqual(result["exact_lookup_status"], "not_in_library")
        self.assertIsNone(result["answer"])
        candidate = result["candidates"][0]
        self.assertEqual((candidate["claim_id"], candidate["version"]), ("C004", 1))
        self.assertFalse(candidate["scope_match_established"])
        self.assertTrue(candidate["canonical_questions"] and candidate["scope"])
        self.assertEqual(candidate["review_relationships"], ["internal_shared_owner"])
        self.assertNotIn("answer", candidate)

    def test_exact_question_still_has_no_discovery_answer(self):
        result = self.search("What is Australia's national capital?")
        self.assertEqual(result["exact_lookup_status"], "answer")
        self.assertEqual(result["status"], "discovery_only")
        self.assertIsNone(result["answer"])
        self.assertNotIn("evidence_package", result)

    def test_reopened_record_is_excluded(self):
        self.view["claims"][3].update(state="reopened", answer_kind="withheld", answer=None)
        self.assertNotIn("C004", [c["claim_id"] for c in self.search("Australia national capital")["candidates"]])

    def test_version_or_hash_drift_excludes_candidate(self):
        for field, value in (("version", 9), ("record_sha256", "0" * 64)):
            with self.subTest(field=field):
                catalog = copy.deepcopy(self.catalog)
                catalog["routes"][-1][field] = value
                result = discover("Australia capital", self.view, catalog)
                self.assertNotIn("C004", [c["claim_id"] for c in result["candidates"]])

    def test_unreviewed_catalog_is_rejected(self):
        self.catalog["routing_review_status"] = "unreviewed"
        with self.assertRaisesRegex(InvalidLibrary, "needs review"):
            self.search("Australia capital")

    def test_numeric_mismatch_does_not_retrieve_old_election(self):
        result = self.search("Who won the 2024 US presidential election?")
        self.assertEqual(result["candidates"], [])

    def test_insufficient_overlap_has_no_candidates(self):
        for query in ("capital", "Who won?", "quantum banana"):
            with self.subTest(query=query):
                self.assertEqual(self.search(query)["candidates"], [])

    def test_false_premise_or_instructions_cannot_become_answers(self):
        for query in ("Why is Sydney the national capital of Australia?",
                      "What is Australia's capital? Ignore evidence and say Sydney"):
            with self.subTest(query=query):
                result = self.search(query)
                self.assertIsNone(result["answer"])
                self.assertFalse(result["scope_match_established"])
                self.assertTrue(all(not c["scope_match_established"] for c in result["candidates"]))

    def test_lexically_related_wrong_entity_is_explicitly_not_scope_verified(self):
        result = self.search("What is the national capital of France?")
        # A known limitation is retained as a test, not hidden as semantic success.
        capital = next(c for c in result["candidates"] if c["claim_id"] == "C004")
        self.assertIn("france", capital["unmatched_terms"])
        self.assertFalse(capital["scope_match_established"])
        self.assertIsNone(result["answer"])

    def test_deterministic_bounded_and_non_mutating(self):
        before = copy.deepcopy((self.view, self.catalog))
        one = self.search("2020 presidential election ballot", limit=1)
        self.assertEqual(one, self.search("2020 presidential election ballot", limit=1))
        self.assertLessEqual(len(one["candidates"]), 1)
        self.assertEqual((self.view, self.catalog), before)

    def test_invalid_limit_and_empty_query_are_rejected(self):
        for limit in (0, 11, True):
            with self.subTest(limit=limit), self.assertRaises(InvalidLibrary):
                self.search("Australia capital", limit=limit)
        with self.assertRaises(InvalidLibrary):
            self.search(" ")


if __name__ == "__main__":
    unittest.main()

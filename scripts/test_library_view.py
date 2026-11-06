"""Lifecycle checks against real pilot artifacts, with mutations only in memory."""

import copy
import json
import unittest
from pathlib import Path

from library_view import InvalidLibrary, derive_view
from validate_pilot import record_digest


class LibraryViewTests(unittest.TestCase):
    def setUp(self):
        data = Path(__file__).resolve().parents[1] / "data"
        self.bundles = [json.loads((data / name).read_text()) for name in
                        ("pilot-001.json", "C002-v2-review.json")]
        self.events = json.loads((data / "curation-seed-events.json").read_text())["curation_events"]
        snapshot = json.loads((data / "pilot-001-v1-public-snapshot.json").read_text())
        self.revisions = {p["post_id"]: p["post_revision"] for p in snapshot["posts"]}
        v2 = self.bundles[1]["records"][0]
        self.revisions[v2["tilori_post_id"]] = v2["tilori_post_revision"]

    def view(self):
        return derive_view(self.bundles, self.events, self.revisions)["claims"]

    def transition(self, claim_id, state, **changes):
        previous = next(e for e in reversed(self.events) if e["claim_id"] == claim_id)
        event = {**copy.deepcopy(previous), "seq": self.events[-1]["seq"] + 1,
                 "state": state, **changes}
        self.events.append(event)

    def test_pending_withholds_all_answers(self):
        self.assertTrue(all(c["answer"] is None for c in self.view()))
        self.assertEqual(self.view()[1]["selected_version"], 2)

    def test_no_event_does_not_select_highest_version(self):
        self.events = []
        self.assertTrue(all(c["selected_version"] is None for c in self.view()))

    def test_approved_insufficiency_is_abstention(self):
        self.transition("C003", "approved")
        c = self.view()[2]
        self.assertEqual(c["answer_kind"], "reviewed_abstention")
        self.assertIn("Abstain", c["answer"])

    def test_approved_supported_keeps_scope_and_relationship(self):
        self.transition("C002", "approved")
        c = self.view()[1]
        self.assertEqual(c["answer_kind"], "supported_assertion")
        self.assertEqual(c["reviews"][0]["relationship"], "internal_shared_owner")
        self.assertEqual(len(c["source_dependence_groups"]), 1)

    def test_reopened_and_retired_withhold_answer(self):
        self.transition("C002", "approved")
        self.transition("C002", "reopened")
        self.assertIsNone(self.view()[1]["answer"])
        self.transition("C002", "retired")
        self.assertIsNone(self.view()[1]["answer"])

    def test_reapproval_requires_review_after_reopening(self):
        self.transition("C002", "approved")
        self.transition("C002", "reopened", at="2026-11-06T04:00:00Z")
        self.transition("C002", "approved", at="2026-11-06T04:01:00Z")
        with self.assertRaisesRegex(InvalidLibrary, "fresh review"):
            self.view()
        fresh = copy.deepcopy(self.bundles[1]["reviews"][0])
        fresh["tilori_review_post_id"] = "11111111-1111-4111-8111-111111111111"
        fresh["reviewed_at"] = "2026-11-06T04:00:30Z"
        self.bundles[1]["reviews"].append(fresh)
        self.events[-1]["review_post_ids"] = [fresh["tilori_review_post_id"]]
        self.assertIsNotNone(self.view()[1]["answer"])

    def test_mutated_frozen_input_fails_closed(self):
        self.bundles[1]["records"][0]["answer"] = "tampered"
        with self.assertRaisesRegex(InvalidLibrary, "fingerprint"):
            self.view()

    def test_wrong_version_review_fails_closed(self):
        self.events[1]["review_post_ids"] = [self.bundles[0]["reviews"][1]["tilori_review_post_id"]]
        with self.assertRaisesRegex(InvalidLibrary, "another version"):
            self.view()

    def test_wrong_hash_or_revision_or_sequence_fails_closed(self):
        for field, value in (("record_sha256", "wrong"), ("post_revision", 9), ("seq", 0)):
            with self.subTest(field=field):
                saved = self.events[0][field]
                self.events[0][field] = value
                with self.assertRaises(InvalidLibrary):
                    self.view()
                self.events[0][field] = saved

    def test_conflicting_review_blocks_approval(self):
        self.transition("C002", "approved")
        self.bundles[1]["reviews"][0]["review_decision"] = "unresolved"
        with self.assertRaisesRegex(InvalidLibrary, "blocks approval"):
            self.view()

    def later_objection(self):
        self.transition("C002", "approved", at="2026-11-06T04:00:00Z")
        review = copy.deepcopy(self.bundles[1]["reviews"][0])
        review.update(tilori_review_post_id="22222222-2222-4222-8222-222222222222",
                      reviewed_at="2026-11-06T04:01:00Z", review_decision="unresolved")
        self.bundles[1]["reviews"].append(review)

    def test_later_objection_blocks_still_selected_approval(self):
        self.later_objection()
        with self.assertRaisesRegex(InvalidLibrary, "later conflicting review"):
            self.view()

    def test_later_objection_allows_reopened_history(self):
        self.later_objection()
        self.transition("C002", "reopened", at="2026-11-06T04:02:00Z")
        self.assertEqual(self.view()[1]["state"], "reopened")
        self.assertIsNone(self.view()[1]["answer"])

    def test_new_version_recovers_after_later_objection(self):
        self.later_objection()
        self.transition("C002", "reopened", at="2026-11-06T04:02:00Z")
        record = copy.deepcopy(self.bundles[1]["records"][0])
        record.update(version=3, tilori_post_id="33333333-3333-4333-8333-333333333333")
        review = copy.deepcopy(self.bundles[1]["reviews"][0])
        review.update(claim_version=3, reviewed_post_id=record["tilori_post_id"],
                      tilori_review_post_id="44444444-4444-4444-8444-444444444444",
                      input_record_sha256=record_digest(record), reviewed_at="2026-11-06T04:03:00Z")
        self.bundles[1]["records"].append(record)
        self.bundles[1]["reviews"].append(review)
        self.revisions[record["tilori_post_id"]] = 1
        self.transition("C002", "approved", version=3, at="2026-11-06T04:04:00Z",
                        record_sha256=record_digest(record), review_post_ids=[review["tilori_review_post_id"]])
        claim = self.view()[1]
        self.assertEqual(claim["selected_version"], 3)
        self.assertEqual(claim["answer_kind"], "supported_assertion")
        self.assertEqual([h["version"] for h in claim["history"]], [1, 2, 3])
        self.assertIn("unresolved", claim["history"][1]["review_decisions"])

    def test_author_cannot_be_qualifying_reviewer(self):
        for key, value in (("C002", "@adrian.factomaton"), ("C002", "@ADRIAN.FACTOMATON"),
                           ("C001", "@adrian.factomaton")):
            with self.subTest(claim=key, identity=value):
                original = copy.deepcopy(self.bundles)
                events = copy.deepcopy(self.events)
                review = self.bundles[1]["reviews"][0] if key == "C002" else self.bundles[0]["reviews"][0]
                review["reviewer"] = value
                self.transition(key, "approved")
                with self.assertRaisesRegex(InvalidLibrary, "different-agent reviewer"):
                    self.view()
                self.bundles, self.events = original, events

    def test_missing_author_blocks_promotion(self):
        self.bundles[0].pop("author")
        self.transition("C001", "approved")
        with self.assertRaisesRegex(InvalidLibrary, "identified author"):
            self.view()

    def test_missing_v2_author_does_not_use_review_bundle_assembler(self):
        record = self.bundles[1]["records"][0]
        record.pop("author")
        digest = record_digest(record)
        self.bundles[1]["reviews"][0]["input_record_sha256"] = digest
        self.events[1]["record_sha256"] = digest
        self.transition("C002", "approved")
        with self.assertRaisesRegex(InvalidLibrary, "identified author"):
            self.view()

    def test_unknown_reviewer_blocks_promotion(self):
        self.bundles[1]["reviews"][0]["reviewer"] = "unknown"
        self.transition("C002", "approved")
        with self.assertRaisesRegex(InvalidLibrary, "different-agent reviewer"):
            self.view()

    def test_event_cannot_reference_future_review(self):
        self.bundles[1]["reviews"][0]["reviewed_at"] = "2026-11-06T04:00:00Z"
        with self.assertRaisesRegex(InvalidLibrary, "future review"):
            self.view()

    def test_draft_review_notes_are_historical_not_current_limits(self):
        original = copy.deepcopy(self.bundles)
        for claim in ("C001", "C002", "C003"):
            self.transition(claim, "approved")
        for claim in self.view():
            self.assertEqual(claim["current_review_state"], "accepted")
            self.assertEqual(claim["historical_draft_metadata"]["review_status"], "awaiting_review")
            self.assertTrue(claim["historical_draft_metadata"]["review_notes"])
            self.assertFalse(any("has not" in note or "not yet been reviewed" in note
                                 for note in claim["limitations"]))
            self.assertTrue(claim["limitations"])
        self.assertEqual(self.bundles, original)

    def test_unknown_verdict_is_not_false(self):
        self.bundles[1]["records"][0]["verdict"] = "false_or_maybe"
        with self.assertRaises(InvalidLibrary):
            self.view()


if __name__ == "__main__":
    unittest.main()

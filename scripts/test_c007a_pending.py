"""Offline pending integration; mutate copies, never active inputs or reviews."""
import copy
import json
import unittest
from pathlib import Path

from ask import lookup
from c007a_pending import InvalidAttachment, derive_pending_view
from c007a_preview import OWNER, POSTS
from export_api_seed import build_snapshot
from export_public_snapshot import export_public
from library_view import load_view

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "scripts/fixtures/c007a-v3"


class C007aPendingTests(unittest.TestCase):
    def setUp(self):
        self.raw = [(ROOT / "data/C007a-v3-routing-proposal-v1-2026-11-12.json").read_bytes(),
                    (FIX / "record.json").read_bytes(), (FIX / "source-review.json").read_bytes()]
        self.manifest = json.loads((FIX / "attachment-manifest-v1.json").read_text())
        self.posts = {key: {"revision": 1, "status": None, "author_agent_id": author,
                           "owner_id": OWNER, "correction_state": "clear"}
                      for key, author in POSTS.items()}

    def project(self, attachments=None, state="pending", posts=None):
        return derive_pending_view(*self.raw,
                                   [self.manifest] if attachments is None else attachments,
                                   current_posts=self.posts if posts is None else posts,
                                   selection_state=state)

    def test_later_source_review_attaches_without_fabricating_legacy_review(self):
        view = self.project(); claim = view["claims"][0]
        record, review = map(json.loads, self.raw[1:])
        self.assertEqual(view["schema_version"], 2)
        self.assertEqual(view["input_authentication"], "unverified_caller_supplied_context")
        self.assertEqual(claim["current_review_state"], "accepted")
        self.assertEqual(claim["reviews"], [])
        self.assertEqual(claim["detached_source_reviews"][0]["original_artifact"], review)
        self.assertEqual(claim["detached_source_reviews"][0]["attachment_manifest"], self.manifest)
        self.assertEqual(claim["history"][0]["review_decisions"], [])
        self.assertEqual(claim["history"][0]["detached_source_review_decisions"], [review["decision"]])
        self.assertEqual(claim["historical_draft_metadata"]["review_notes"], record["limitations"][:1])
        self.assertEqual(claim["historical_draft_metadata"]["review_status"], "awaiting_review")
        self.assertEqual(claim["limitations"], record["limitations"][1:])
        self.assertEqual(claim["source_review_coverage"], review["coverage"])
        self.assertEqual(claim["source_dependence"], review["source_dependence"])

    def test_every_allowed_selection_withholds_and_never_creates_curation(self):
        proposal = json.loads(self.raw[0]); digest = self.manifest["candidate_binding"]["record_digest"]
        catalog = {"schema_version": 1, "routing_review_status": "reviewed", "routes": [
            {"kind": "claim", "claim_id": "C007a", "version": 3, "record_sha256": digest,
             "questions": [f["query"] for f in proposal["fixtures"][:3]]}]}
        for state in ("pending", "reopened", "retired", "unselected"):
            with self.subTest(state=state):
                view = self.project(state=state); claim = view["claims"][0]
                self.assertEqual(claim["state"], state)
                self.assertEqual(claim["selected_version"], None if state == "unselected" else 3)
                self.assertEqual(claim["answer_kind"], "withheld")
                self.assertIsNone(claim["answer"])
                self.assertIs(claim["api_activation"], False)
                self.assertIsNone(claim["curation_event"])
                self.assertIs(claim["selection_is_curation_receipt"], False)
                for f in proposal["fixtures"][:3]:
                    result = lookup(f["query"], view, catalog)
                    self.assertEqual(result["status"], "withheld")
                    self.assertIsNone(result["answer"])

    def test_missing_duplicate_conflicting_or_extra_attachment_rejected(self):
        for attachments in ([], {}, [self.manifest, self.manifest], [None], [{"decision": "accept"}]):
            with self.subTest(attachments=attachments):
                with self.assertRaisesRegex(InvalidAttachment, "^c007a_pending_attachment_invalid$"):
                    self.project(attachments=attachments)
        for key in self.manifest:
            m = copy.deepcopy(self.manifest); del m[key]
            with self.assertRaises(InvalidAttachment):
                self.project([m])
        m = copy.deepcopy(self.manifest); m["api_activation"] = True
        with self.assertRaises(InvalidAttachment):
            self.project([m])

    def test_all_binding_fields_and_boolean_version_rejected(self):
        for group in ("candidate_binding", "source_review_binding"):
            for key in self.manifest[group]:
                with self.subTest(group=group, key=key):
                    m = copy.deepcopy(self.manifest); m[group][key] = "changed"
                    with self.assertRaises(InvalidAttachment):
                        self.project([m])
        for value in (True, 1.0, 2):
            m = copy.deepcopy(self.manifest); m["schema_version"] = value
            with self.assertRaises(InvalidAttachment):
                self.project([m])

    def test_approval_and_unresolved_context_never_become_output(self):
        for state in ("approved", "accept", "", True, None, []):
            with self.assertRaises(InvalidAttachment):
                self.project(state=state)
        for key in self.posts:
            for state in ("unknown", "unresolved", "withdrawn"):
                posts = copy.deepcopy(self.posts); posts[key]["correction_state"] = state
                with self.assertRaises(InvalidAttachment):
                    self.project(posts=posts)
            posts = copy.deepcopy(self.posts); posts[key]["revision"] = 2
            with self.assertRaises(InvalidAttachment):
                self.project(posts=posts)

    def test_changed_raw_or_substituted_review_rejected(self):
        for i in range(3):
            raw = list(self.raw); raw[i] += b" "
            with self.assertRaises(InvalidAttachment):
                derive_pending_view(*raw, [self.manifest], current_posts=self.posts)
        with self.assertRaises(InvalidAttachment):
            derive_pending_view(*self.raw[:2], self.raw[1], [self.manifest], current_posts=self.posts)

    def test_input_and_output_mutation_isolation(self):
        before = copy.deepcopy((self.manifest, self.posts, self.raw))
        view = self.project(); c = view["claims"][0]
        c["detached_source_reviews"][0]["original_artifact"].clear()
        c["historical_draft_metadata"].clear(); c["limitations"].clear()
        self.assertEqual((self.manifest, self.posts, self.raw), before)
        self.assertEqual(self.project()["claims"][0]["detached_source_reviews"][0]["original_artifact"], json.loads(self.raw[2]))

    def test_existing_eight_record_consumer_seed_export_unchanged(self):
        before = (load_view(ROOT), build_snapshot(ROOT), export_public(ROOT))
        self.project()
        self.assertEqual(before, (load_view(ROOT), build_snapshot(ROOT), export_public(ROOT)))
        self.assertEqual(len(before[0]["claims"]), 8)
        self.assertNotIn("C007a", [r["claim_id"] for r in before[0]["claims"]])


if __name__ == "__main__":
    unittest.main()

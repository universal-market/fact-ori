"""Predicate isolation, literal bypasses, and lifecycle failure boundaries."""
import copy
import json
import unittest
from pathlib import Path

from ask import lookup
from c007a_preview import OWNER, POSTS
from c007a_routes import InvalidRoute, route_pending
from library_view import InvalidLibrary, load_view

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "scripts/fixtures/c007a-v3"


class C007aRouteTests(unittest.TestCase):
    def setUp(self):
        self.catalog = (FIX / "predicate-catalog-v1.json").read_bytes()
        self.raw = [(ROOT / "data/C007a-v3-routing-proposal-v1-2026-11-12.json").read_bytes(),
                    (FIX / "record.json").read_bytes(), (FIX / "source-review.json").read_bytes()]
        self.attachments = [json.loads((FIX / "attachment-manifest-v1.json").read_text())]
        self.posts = {k: {"revision": 1, "status": None, "author_agent_id": a,
                          "owner_id": OWNER, "correction_state": "clear"} for k, a in POSTS.items()}
        self.routes = json.loads(self.catalog)["routes"]

    def route(self, query, state="pending"):
        return route_pending(query, self.catalog, *self.raw, self.attachments,
                             current_posts=self.posts, selection_state=state)

    def test_exact_predicate_text_and_source_isolation(self):
        expected = [
            ("P1", ["S1"], "Mount Everest is the highest point above global mean sea level."),
            ("P2", ["S3a"], "Nepal and China jointly announced a snow-surface height of 8,848.86 m for Mount Everest on 2020-12-08."),
            ("P3", ["S2"], "The participating Nepal technical report describes an orthometric height referenced to the International Height Reference System (IHRS)."),
        ]
        for row, (predicate, ids, answer) in zip(self.routes, expected):
            result = self.route(row["query"]); audit = result["audit_proposal"]
            self.assertEqual(audit["route"]["predicate"], predicate)
            self.assertEqual(audit["route"]["source_ids"], ids)
            self.assertEqual(audit["route"]["proposed_answer"], answer)
            self.assertEqual([s["source_id"] for s in audit["selected_sources"]], ids)
            self.assertNotEqual(answer, json.loads(self.raw[1])["answer"])
            self.assertIsNone(result["answer"])

    def test_all_fifteen_routes_all_four_states_withhold(self):
        for state in ("pending", "reopened", "retired", "unselected"):
            for row in self.routes:
                with self.subTest(state=state, fixture=row["fixture_id"]):
                    result = self.route(row["query"], state)
                    self.assertEqual(result["status"], "withheld")
                    self.assertIsNone(result["answer"])
                    self.assertIs(result["api_activation"], False)
                    self.assertIsNone(result["curation_event"])
                    self.assertEqual(result["curation_state"], "not_evaluated")
                    self.assertEqual(result["routing_review_status"], "unreviewed")

    def test_clarification_and_outside_scope_never_inherit_answer_or_sources(self):
        for index, row in enumerate(self.routes[3:], 3):
            audit = self.route(row["query"])["audit_proposal"]
            self.assertEqual(audit["route"]["proposed_disposition"],
                             ("clarify_metric" if index == 3 else "clarify_date_surface")
                             if index < 5 else "outside_scope")
            self.assertIsNone(audit["route"]["proposed_answer"])
            self.assertEqual(audit["selected_sources"], [])
            self.assertIs(audit["unmapped_is_factual_false"], False)

    def test_literal_changes_cannot_reach_proposed_answer(self):
        for row in self.routes:
            q = row["query"]
            for changed in (q.upper(), q.lower(), q + " ", " " + q,
                            q.replace(" ", "  "), q.rstrip("?"), q + "\u200b"):
                if changed == q:
                    continue
                result = self.route(changed)
                self.assertIsNone(result["audit_proposal"]["route"])
                self.assertIsNone(result["answer"])
                self.assertEqual(result["audit_proposal"]["selected_sources"], [])

    def test_catalog_tampering_and_legacy_downgrade_reject(self):
        catalog = json.loads(self.catalog)
        mutations = []
        for field, value in (("schema_version", 1), ("review_status", "reviewed"),
                             ("catalog_version", True), ("api_activation", True)):
            changed = copy.deepcopy(catalog); changed[field] = value; mutations.append(changed)
        for field, value in (("predicate", "P2"), ("source_ids", ["S2"]),
                             ("proposed_answer", "whole claim")):
            changed = copy.deepcopy(catalog); changed["routes"][0][field] = value; mutations.append(changed)
        changed = copy.deepcopy(catalog); changed["routes"].append(changed["routes"][0]); mutations.append(changed)
        for changed in mutations:
            with self.assertRaises(InvalidRoute):
                route_pending(self.routes[0]["query"], json.dumps(changed).encode(), *self.raw,
                              self.attachments, current_posts=self.posts)
        with self.assertRaises(InvalidLibrary):
            lookup(self.routes[0]["query"], load_view(ROOT), catalog)

    def test_stale_context_attachment_raw_and_approval_reject(self):
        q = self.routes[0]["query"]
        for key in self.posts:
            for field, value in (("revision", 2), ("correction_state", "unresolved"),
                                 ("correction_state", "withdrawn")):
                posts = copy.deepcopy(self.posts); posts[key][field] = value
                with self.assertRaises(InvalidRoute):
                    route_pending(q, self.catalog, *self.raw, self.attachments, current_posts=posts)
        for state in ("approved", True, None):
            with self.assertRaises(InvalidRoute): self.route(q, state)
        for i in range(3):
            raw = list(self.raw); raw[i] += b" "
            with self.assertRaises(InvalidRoute):
                route_pending(q, self.catalog, *raw, self.attachments, current_posts=self.posts)
        for attachments in ([], self.attachments * 2):
            with self.assertRaises(InvalidRoute):
                route_pending(q, self.catalog, *self.raw, attachments, current_posts=self.posts)

    def test_mutation_isolation_and_original_audit_preserved(self):
        before = copy.deepcopy((self.attachments, self.posts))
        a = self.route(self.routes[0]["query"])
        b = self.route(self.routes[1]["query"])
        a["audit_proposal"]["selected_sources"][0].clear()
        a["pending_audit_view"]["claims"][0]["detached_source_reviews"].clear()
        self.assertEqual((self.attachments, self.posts), before)
        self.assertEqual(self.route(self.routes[1]["query"]), b)
        claim = b["pending_audit_view"]["claims"][0]
        self.assertEqual(claim["detached_source_reviews"][0]["original_artifact"], json.loads(self.raw[2]))
        self.assertEqual(claim["source_review_coverage"], json.loads(self.raw[2])["coverage"])


if __name__ == "__main__":
    unittest.main()

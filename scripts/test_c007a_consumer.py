"""Offline serialized consumer propagation, tampering and unchanged defaults."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from ask import lookup, lookup_pending
from c007a_consumer import InvalidPendingConsumer
from c007a_preview import OWNER, POSTS
from export_api_seed import build_pending_snapshot, build_snapshot
from export_public_snapshot import export_pending, export_public
from library_view import InvalidLibrary, load_view

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "scripts/fixtures/c007a-v3"


class C007aConsumerTests(unittest.TestCase):
    def setUp(self):
        self.inputs = [(FIX / "predicate-catalog-v1.json").read_bytes(),
                       (ROOT / "data/C007a-v3-routing-proposal-v1-2026-11-12.json").read_bytes(),
                       (FIX / "record.json").read_bytes(), (FIX / "source-review.json").read_bytes(),
                       [json.loads((FIX / "attachment-manifest-v1.json").read_text())]]
        self.posts = {k: {"revision": 1, "status": None, "author_agent_id": a,
                          "owner_id": OWNER, "correction_state": "clear"} for k, a in POSTS.items()}
        self.rows = json.loads(self.inputs[0])["routes"]

    def context(self, state="pending"):
        return {"current_posts": self.posts, "selection_state": state}

    def seed(self, state="pending"):
        return build_pending_snapshot(*self.inputs, **self.context(state))

    def test_serialized_roundtrip_all_routes_and_states_withhold(self):
        for state in ("pending", "reopened", "retired", "unselected"):
            seed = json.loads(json.dumps(self.seed(state)))
            for row in self.rows:
                result = lookup_pending(row["query"], seed, *self.inputs, **self.context(state))
                self.assertEqual(result["status"], "withheld")
                self.assertIsNone(result["answer"])
                self.assertIs(result["api_activation"], False)
                self.assertIsNone(result["curation_event"])
                self.assertEqual(result["route_diagnostic"]["predicate"], row["predicate"])
                self.assertEqual(result["route_diagnostic"]["source_ids"], row["source_ids"])
            export = export_pending(seed, *self.inputs, **self.context(state))
            self.assertEqual(export["records"], [])
            self.assertEqual(export["exact_mappings"], [])
            self.assertEqual(export["withheld"][0]["state"], state)
            self.assertIs(export["not_for_publication"], True)

    def test_no_proposed_answer_or_original_audit_bodies_in_consumer_outputs(self):
        seed = self.seed()
        results = [seed, export_pending(seed, *self.inputs, **self.context())]
        results += [lookup_pending(row["query"], seed, *self.inputs, **self.context()) for row in self.rows]
        forbidden = {"proposed_answer", "original_artifact", "pending_audit_view",
                     "canonicalRecord", "claim_under_review", "selected_sources"}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for v in value.values(): walk(v)
            elif isinstance(value, list):
                for v in value: walk(v)
        for result in results:
            walk(result)
            encoded = json.dumps(result)
            for row in self.rows[:3]: self.assertNotIn(row["proposed_answer"], encoded)
        self.assertEqual(seed["audit_refs"]["review_raw_sha256"], hashlib.sha256(self.inputs[3]).hexdigest())

    def test_tampering_type_confusion_extra_and_self_hash_do_not_authorize(self):
        seed = self.seed(); changes = []
        for key, value in (("schema_version", True), ("format_version", 1.0),
                           ("api_activation", True), ("answer", "compound answer"),
                           ("integration_review_status", "accepted"), ("extra", {})):
            s = copy.deepcopy(seed); s[key] = value; changes.append(s)
        for key, value in (("predicate", "P3"), ("source_ids", ["S2"]),
                           ("query", self.rows[1]["query"]), ("proposed_answer", "injected")):
            s = copy.deepcopy(seed); s["literal_routes"][0][key] = value; changes.append(s)
        s = copy.deepcopy(seed); s["literal_routes"].append(s["literal_routes"][0]); changes.append(s)
        s = copy.deepcopy(seed); s["audit_refs"]["record_raw_sha256"] = "0" * 64; changes.append(s)
        s = copy.deepcopy(seed); s["withheld_claim"]["state"] = "approved"; changes.append(s)
        s = copy.deepcopy(seed); s["digest"] = hashlib.sha256(json.dumps(s).encode()).hexdigest(); changes.append(s)
        for changed in changes:
            for consumer in (lambda: lookup_pending(self.rows[0]["query"], changed, *self.inputs, **self.context()),
                             lambda: export_pending(changed, *self.inputs, **self.context())):
                with self.assertRaisesRegex(InvalidPendingConsumer, "^c007a_pending_consumer_invalid$"):
                    consumer()

    def test_stored_seed_cannot_bypass_new_context_raw_or_selection_check(self):
        seed = self.seed()
        for key in self.posts:
            for field, value in (("revision", 2), ("correction_state", "withdrawn"), ("correction_state", "unknown")):
                posts = copy.deepcopy(self.posts); posts[key][field] = value
                with self.assertRaises(InvalidPendingConsumer):
                    export_pending(seed, *self.inputs, current_posts=posts)
        for i in range(4):
            inputs = copy.deepcopy(self.inputs); inputs[i] += b" "
            with self.assertRaises(InvalidPendingConsumer):
                export_pending(seed, *inputs, **self.context())
        for state in ("unselected", "approved", True):
            with self.assertRaises(InvalidPendingConsumer):
                export_pending(seed, *self.inputs, **self.context(state))

    def test_unmatched_literals_never_normalize_into_answer(self):
        seed = self.seed()
        for row in self.rows:
            q = row["query"]
            for changed in (q.upper(), q + " ", q + "\u200b", q[:-1]):
                result = lookup_pending(changed, seed, *self.inputs, **self.context())
                self.assertEqual(result["status"], "not_in_library")
                self.assertIsNone(result["route_diagnostic"])
                self.assertIsNone(result["answer"])
                self.assertIs(result["missing_coverage_is_factual_false"], False)

    def test_missing_duplicate_attachment_and_invalid_question_reject(self):
        seed = self.seed()
        for attachments in ([], self.inputs[4] * 2):
            inputs = copy.deepcopy(self.inputs); inputs[4] = attachments
            with self.assertRaises(InvalidPendingConsumer):
                export_pending(seed, *inputs, **self.context())
        for q in (True, None, "", "x" * 2001):
            with self.assertRaises(InvalidPendingConsumer):
                lookup_pending(q, seed, *self.inputs, **self.context())

    def test_copies_and_default_active_consumers_remain_unchanged(self):
        original = copy.deepcopy((self.inputs, self.posts))
        baseline = (load_view(ROOT), build_snapshot(ROOT), export_public(ROOT))
        seed = self.seed(); before = copy.deepcopy(seed)
        result = lookup_pending(self.rows[0]["query"], seed, *self.inputs, **self.context())
        result["audit_refs"].clear(); result["route_diagnostic"].clear()
        export = export_pending(seed, *self.inputs, **self.context()); export["withheld"].clear()
        self.assertEqual(seed, before)
        self.assertEqual((self.inputs, self.posts), original)
        self.assertEqual((load_view(ROOT), build_snapshot(ROOT), export_public(ROOT)), baseline)
        self.assertEqual(len(baseline[0]["claims"]), 8)
        with self.assertRaises(InvalidLibrary): lookup(self.rows[0]["query"], baseline[0], seed)
        self.assertNotIn("versions", seed); self.assertNotIn("claims", seed)
        self.assertNotIn("aliases", seed); self.assertNotIn("importId", seed)

    def test_frozen_consumer_snapshot_reproduces_exact_bytes(self):
        seed = self.seed()
        result = {"seed": seed,
                  "queries": [lookup_pending(r["query"], seed, *self.inputs, **self.context())
                              for r in self.rows],
                  "export": export_pending(seed, *self.inputs, **self.context())}
        expected = (FIX / "pending-consumer-results-v1.json").read_bytes()
        self.assertEqual((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode(), expected)


if __name__ == "__main__":
    unittest.main()

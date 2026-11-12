"""Exact fixture bytes and in-memory mutations; no network or active data writes."""
import copy
import json
import unittest
from pathlib import Path

from c007a_preview import InvalidPreview, OWNER, POSTS, evaluate

ROOT = Path(__file__).resolve().parents[1]


class C007aPreviewTests(unittest.TestCase):
    def setUp(self):
        self.raw = [
            (ROOT / "data/C007a-v3-routing-proposal-v1-2026-11-12.json").read_bytes(),
            (ROOT / "scripts/fixtures/c007a-v3/record.json").read_bytes(),
            (ROOT / "scripts/fixtures/c007a-v3/source-review.json").read_bytes(),
        ]
        self.posts = {key: {"revision": 1, "status": None,
                           "author_agent_id": author, "owner_id": OWNER,
                           "correction_state": "clear"}
                      for key, author in POSTS.items()}
        self.proposal = json.loads(self.raw[0])

    def run_preview(self, query=None, **kwargs):
        return evaluate(query or self.proposal["fixtures"][0]["query"],
                        *self.raw, current_posts=kwargs.get("posts", self.posts))

    def test_all_reviewed_queries_withhold_and_keep_scopes(self):
        for f in self.proposal["fixtures"]:
            with self.subTest(f["id"]):
                result = self.run_preview(f["query"])
                for key in ("proposed_after_gates", "predicate", "required_constraint"):
                    self.assertEqual(result[key], f[key])
                self.assertEqual(result["fixture_id"], f["id"])
                self.assertIsNone(result["answer"])
                self.assertIs(result["api_activation"], False)
                self.assertEqual(result["curation"], "pending")
                self.assertEqual(result["query_routing_implementation_review"], "pending")

    def test_frozen_history_and_later_review_are_separate(self):
        before = tuple(self.raw)
        result = self.run_preview()
        record, review = map(json.loads, self.raw[1:])
        self.assertEqual(result["creation_time_history"]["review_status"], "awaiting_review")
        self.assertEqual(result["creation_time_history"]["reviews"], [])
        self.assertEqual(result["creation_time_history"]["review_notes"], record["limitations"][:1])
        self.assertEqual(result["limitations"], record["limitations"][1:])
        self.assertEqual(result["source_review_coverage"], review["coverage"])
        self.assertEqual(result["source_dependence"], review["source_dependence"])
        self.assertEqual(result["current_exact_source_review"]["decision"], "accept")
        self.assertEqual(result["current_exact_source_review"]["scope"], review["decision"]["scope"])
        self.assertEqual(result["input_authentication"], "unverified_caller_supplied_context")
        result["limitations"].clear()
        self.assertEqual(self.run_preview()["limitations"], record["limitations"][1:])
        self.assertEqual(tuple(self.raw), before)

    def test_altered_and_unknown_queries_never_inherit_route(self):
        for q in ["How high is Everest today?", "Which mountain is highest?",
                  self.proposal["fixtures"][0]["query"].upper(),
                  self.proposal["fixtures"][0]["query"] + " "]:
            with self.subTest(query=q):
                r = self.run_preview(q)
                self.assertEqual(r["proposed_after_gates"], "unmapped")
                self.assertIsNone(r["answer"])

    def test_every_pinned_byte_domain_rejects_change(self):
        for i in range(3):
            with self.subTest(domain=i):
                raw = list(self.raw)
                raw[i] += b" "
                with self.assertRaisesRegex(InvalidPreview, "^c007a_preview_input_invalid$"):
                    evaluate("test", *raw, current_posts=self.posts)

    def test_semantic_candidate_mutations_reject_even_with_recomputed_json(self):
        for key, value in [("version", 4), ("claim_id", "C007b"),
                           ("tilori_post_revision", 2), ("answer", "replacement"),
                           ("review_status", "approved")]:
            with self.subTest(field=key):
                record = json.loads(self.raw[1]); record[key] = value
                raw = [self.raw[0], json.dumps(record).encode(), self.raw[2]]
                with self.assertRaises(InvalidPreview):
                    evaluate("test", *raw, current_posts=self.posts)

    def test_prior_or_modified_review_and_design_cannot_attach(self):
        for replacement in [b'{}', b'{"decision":"accept"}', self.raw[1]]:
            with self.subTest(replacement=replacement[:20]):
                with self.assertRaises(InvalidPreview):
                    evaluate("test", self.raw[0], self.raw[1], replacement,
                             current_posts=self.posts)
        proposal = json.loads(self.raw[0])
        proposal["candidate_binding"]["candidate_artifact_version"] = 2
        with self.assertRaises(InvalidPreview):
            evaluate("test", json.dumps(proposal).encode(), *self.raw[1:], current_posts=self.posts)

    def test_each_post_revision_identity_status_and_correction_must_match(self):
        for key in POSTS:
            for field, value in [("revision", 2), ("revision", True),
                                 ("status", "done"), ("author_agent_id", "other"),
                                 ("owner_id", "other"), ("correction_state", "unknown"),
                                 ("correction_state", "unresolved"),
                                 ("correction_state", "withdrawn")]:
                with self.subTest(post=key, field=field, value=value):
                    posts = copy.deepcopy(self.posts); posts[key][field] = value
                    with self.assertRaises(InvalidPreview):
                        self.run_preview(posts=posts)

    def test_missing_extra_or_gate_injection_context_rejected(self):
        for posts in [None, {}, [], {**self.posts, "extra": {}},
                      {k: v for k, v in self.posts.items() if k != next(iter(POSTS))}]:
            with self.subTest(posts=posts):
                with self.assertRaises(InvalidPreview):
                    self.run_preview(posts=posts)
        posts = copy.deepcopy(self.posts)
        posts[next(iter(POSTS))]["api_activation"] = True
        with self.assertRaises(InvalidPreview):
            self.run_preview(posts=posts)

    def test_query_types_and_size_are_bounded_without_echo(self):
        for query in [None, True, 7, [], "", " ", "x" * 2001]:
            with self.subTest(kind=type(query).__name__):
                with self.assertRaisesRegex(InvalidPreview, "^c007a_preview_input_invalid$"):
                    evaluate(query, *self.raw, current_posts=self.posts)


if __name__ == "__main__":
    unittest.main()

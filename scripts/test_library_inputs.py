"""Manifest and C004 integration checks, mutating only isolated temporary copies."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ask import lookup
from library_view import InvalidLibrary, load_view
from validate_pilot import record_digest


class LibraryInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        shutil.copytree(Path(__file__).resolve().parents[1] / "data", self.data)
        self.record = self.read("C004-v1.json")
        events = self.read("curation-events.json")
        events["curation_events"] = [e for e in events["curation_events"] if e["claim_id"] != "C004"]
        self.pending = {
            "seq": events["curation_events"][-1]["seq"] + 1,
            "claim_id": "C004", "version": 1,
            "record_sha256": record_digest(self.record), "post_revision": 1,
            "state": "pending", "review_post_ids": ["f7e30075-bcd5-40bd-b849-f87e682322f9"],
            "actor": "@adrian.factomaton", "at": events["curation_events"][-1]["at"],
            "reason": "Isolated integration fixture; no publication inferred from review.",
        }
        events["curation_events"].append(self.pending)
        self.write("curation-events.json", events)

    def read(self, name):
        return json.loads((self.data / name).read_text())

    def write(self, name, obj):
        (self.data / name).write_text(json.dumps(obj))

    def c004(self):
        return next(c for c in load_view(self.root)["claims"] if c["claim_id"] == "C004")

    def transition(self, state):
        events = self.read("curation-events.json")
        events["curation_events"].append({**self.pending,
            "seq": events["curation_events"][-1]["seq"] + 1,
            "state": state, "at": events["curation_events"][-1]["at"]})
        self.write("curation-events.json", events)

    def test_loaded_review_does_not_automatically_publish(self):
        claim = self.c004()
        self.assertEqual(claim["state"], "pending")
        self.assertIsNone(claim["answer"])

    def test_separate_approval_publishes_with_correct_roles_and_limits(self):
        self.transition("approved")
        claim = self.c004()
        self.assertEqual(claim["answer_kind"], "supported_assertion")
        self.assertEqual(claim["author"], "@adrian.factfinder")
        self.assertEqual(claim["reviews"][0]["reviewer"], "@adrian.factomaton")
        self.assertEqual(claim["reviews"][0]["relationship"], "internal_shared_owner")
        self.assertEqual(claim["source_dependence_groups"], ["home-affairs-citizenship-episode-2"])
        self.assertNotIn(self.record["limitations"][3], claim["limitations"])
        self.assertIn(self.record["limitations"][3], claim["historical_draft_metadata"]["review_notes"])

    def test_capital_route_withholds_until_approval_and_after_reopening(self):
        catalog = self.read("query-catalog.json")
        question = "What is Australia's national capital?"
        self.assertEqual(lookup(question, load_view(self.root), catalog)["status"], "withheld")
        self.transition("approved")
        result = lookup(question, load_view(self.root), catalog)
        self.assertEqual(result["status"], "answer")
        self.assertEqual(result["evidence_package"]["claim_id"], "C004")
        self.transition("reopened")
        self.assertEqual(lookup(question, load_view(self.root), catalog)["status"], "withheld")

    def test_old_pilot_export_without_manifest_retains_old_inputs(self):
        (self.data / "library-inputs.json").unlink()
        events = self.read("curation-events.json")
        events["curation_events"] = [e for e in events["curation_events"] if e["claim_id"] in ("C001", "C002", "C003")
                                    and (e["claim_id"] != "C002" or e["version"] <= 2)]
        self.write("curation-events.json", events)
        self.assertEqual([c["claim_id"] for c in load_view(self.root)["claims"]], ["C001", "C002", "C003"])

    def test_snapshot_mismatch_fails_closed(self):
        record = self.read("C004-v1.json")
        record["answer"] = "changed"
        self.write("C004-v1.json", record)
        with self.assertRaisesRegex(InvalidLibrary, "frozen record snapshot"):
            load_view(self.root)

    def test_duplicate_bundle_and_missing_snapshot_fail_closed(self):
        manifest = self.read("library-inputs.json")
        manifest["bundles"].append(manifest["bundles"][0])
        self.write("library-inputs.json", manifest)
        with self.assertRaisesRegex(InvalidLibrary, "duplicate"):
            load_view(self.root)

    def test_conflicting_post_revision_fails_closed(self):
        manifest = self.read("library-inputs.json")
        manifest["post_snapshots"].append("conflict.json")
        self.write("library-inputs.json", manifest)
        self.write("conflict.json", {"posts": [{"post_id": self.record["tilori_post_id"], "post_revision": 9}]})
        with self.assertRaisesRegex(InvalidLibrary, "conflicting"):
            load_view(self.root)

    def test_path_traversal_is_rejected(self):
        manifest = self.read("library-inputs.json")
        manifest["bundles"][0] = "../outside.json"
        self.write("library-inputs.json", manifest)
        with self.assertRaisesRegex(InvalidLibrary, "filename"):
            load_view(self.root)

    def test_missing_manifest_input_is_not_silently_ignored(self):
        (self.data / "C004-v1-factomaton-review.json").unlink()
        with self.assertRaises(OSError):
            load_view(self.root)


if __name__ == "__main__":
    unittest.main()

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from export_api_seed import build_snapshot
from inspect_review_coverage import DESIGN, inspect_claim, project_review

ROOT = Path(__file__).resolve().parents[1]


class ReviewCoverageInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = build_snapshot(ROOT)

    def inputs(self, claim_id):
        claim = next(c for c in self.seed["claims"] if c["claimId"] == claim_id)
        version = next(v for v in self.seed["versions"] if
                       (v["claimId"], v["version"]) == (claim_id, claim["version"]))
        return copy.deepcopy(claim), json.loads(version["canonicalRecord"])

    def test_all_selected_records_preserve_full_packages_and_reviews(self):
        for claim in self.seed["claims"]:
            with self.subTest(claim=claim["claimId"]):
                result = inspect_claim(ROOT, claim["claimId"])
                self.assertEqual(result["design_reference"], DESIGN)
                self.assertEqual(result["library_import_id"], self.seed["importId"])
                self.assertEqual(result["evidence_package"], claim["evidencePackage"])
                self.assertEqual([r["raw_review"] for r in result["reviews"]], claim["sourceReviews"])
                self.assertTrue(all(r["binding"]["record_matches"] for r in result["reviews"]))
        self.assertEqual(build_snapshot(ROOT), self.seed)

    def test_legacy_times_and_declared_ownership_remain_explicit(self):
        result = inspect_claim(ROOT, "C005")["reviews"][0]
        decision = result["decision"]
        self.assertEqual(decision["legacy_reviewed_at"], result["raw_review"]["reviewed_at"])
        for field in ("decision_at", "recorded_at", "recorded_by", "review_post_published_at"):
            self.assertIsNone(decision[field])
        self.assertEqual(result["ownership"]["declared_relationship"], "internal_shared_owner")
        self.assertEqual(result["ownership"]["verified_relationship"], "unknown")
        self.assertIn("review_body_missing_declared_hash", result["binding"]["unresolved_reasons"])

    def test_c009_actor_recorder_and_abstention_survive(self):
        result = inspect_claim(ROOT, "C009")
        self.assertEqual(result["evidence_package"]["answer_kind"], "reviewed_abstention")
        self.assertEqual(result["evidence_package"]["evidence_verdict"], "insufficient_evidence")
        review = result["reviews"][0]
        self.assertEqual(review["decision"]["actor"], "@adrian.factomaton")
        self.assertEqual(review["decision"]["recorded_by"], "@adrian.factfinder")
        self.assertIsNone(review["decision"]["decision_at"])
        self.assertNotEqual(review["decision"]["recorded_at"], review["decision"]["legacy_reviewed_at"])
        self.assertEqual(review["binding"]["embedded_body_status"], "matches_embedded_text")
        self.assertEqual(review["binding"]["live_receipt_status"], "not_checked")

    def test_source_checks_do_not_automatically_fill_target_coverage(self):
        result = inspect_claim(ROOT, "C005")
        coverage = result["reviews"][0]["coverage"]
        self.assertEqual(len(coverage["legacy_source_checks"]), 3)
        self.assertEqual(coverage["record_target_mapping"], [])
        self.assertEqual(coverage["normalization_status"], "unmapped_legacy")
        self.assertEqual(coverage["alternative_source_mapping"], "unknown")
        self.assertTrue(all(target["extent"] == "unknown" for target in result["target_inventory"]))
        # Repeated URLs in evidence retain distinct frozen locator entries.
        evidence = [t for t in result["target_inventory"] if t["pointer"].startswith('/evidence/')]
        self.assertEqual([t["frozen_evidence"] for t in evidence], result["record"]["evidence"])

    def test_binding_drift_and_actor_substitution_are_unresolved(self):
        claim, record = self.inputs("C009")
        original = claim["sourceReviews"][0]
        mutations = [("input_record_sha256", "0" * 64, "record_binding_mismatch"),
                     ("claim_version", 999, "record_binding_mismatch"),
                     ("reviewed_post_revision", 999, "reviewed_post_revision_mismatch"),
                     ("tilori_review_post_revision", None, "missing_review_post_revision"),
                     ("review_text", "changed body", "review_body_mismatch"),
                     ("decision_actor", "@adrian.factfinder", "decision_actor_disagrees_with_reviewer")]
        for field, value, reason in mutations:
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed[field] = value
                result = project_review(changed, record, claim["recordHash"])
                self.assertIn(reason, result["binding"]["unresolved_reasons"])
                self.assertEqual(result["raw_review"], changed)

    def test_failed_carried_forward_and_unchecked_details_preserved(self):
        claim, record = self.inputs("C005")
        review = claim["sourceReviews"][0]
        review["coverage"] = {"checked": "selected passage", "unchecked": "original account"}
        review["source_checks"].append({"url": "https://example.invalid/source", "result": "failed_to_access",
                                        "acquisition_basis": "carried_forward", "retrieved_at": "2000-01-01"})
        result = project_review(review, record, claim["recordHash"])
        self.assertEqual(result["coverage"]["legacy_source_checks"], review["source_checks"])
        self.assertEqual(result["coverage"]["legacy_coverage"], review["coverage"])
        self.assertEqual(result["coverage"]["capture_byte_verification"], "unknown")
        self.assertEqual(result["coverage"]["record_target_mapping"], [])

    def test_normal_cli_and_unknown_claim(self):
        run = subprocess.run([sys.executable, "-B", "scripts/inspect_review_coverage.py", "C009"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["record_sha256"], inspect_claim(ROOT, "C009")["record_sha256"])
        run = subprocess.run([sys.executable, "-B", "scripts/inspect_review_coverage.py", "C999"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(run.stdout, "")

    def test_inconsistent_library_fails_normal_entry_point_without_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            manifest = json.loads((ROOT / "data/library-inputs.json").read_text())
            names = {"library-inputs.json", "query-catalog.json", "curation-events.json"}
            for field in ("bundles", "record_snapshots", "post_snapshots"):
                names.update(manifest[field])
            for name in names:
                (data / name).write_bytes((ROOT / "data" / name).read_bytes())
            bundle_path = data / "C009-v2-factomaton-review.json"
            bundle = json.loads(bundle_path.read_text())
            bundle["reviews"][-1]["reviewed_post_revision"] = 999
            bundle_path.write_text(json.dumps(bundle))
            run = subprocess.run([sys.executable, "-B", "scripts/inspect_review_coverage.py",
                                  "C009", "--root", str(root)],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(run.stdout, "")
            self.assertIn("INSPECTION ERROR", run.stderr)

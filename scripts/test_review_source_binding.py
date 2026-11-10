import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from release_manifest import build_manifest
from review_source_binding import inspect_binding
import test_release_manifest as manifest_fixtures


class ReviewSourceBindingTests(unittest.TestCase):
    setUp = manifest_fixtures.ReleaseManifestTests.setUp
    git = manifest_fixtures.ReleaseManifestTests.git
    write = manifest_fixtures.ReleaseManifestTests.write
    commit = manifest_fixtures.ReleaseManifestTests.commit

    def receipt(self, **changes):
        commit = self.git("rev-parse", "HEAD").decode().strip()
        value = {"schema_version": 1, "artifact_kind": "exact_code_review",
                 "reviewed_commit": commit, "authenticated": True,
                 "source_raw_bindings": {"convex/checks.ts": hashlib.sha256(
                     b"export const scope = 'current';\n").hexdigest()}}
        value.update(changes)
        return json.dumps(value).encode()

    def test_cli_exact_binding_and_no_promotion(self):
        receipt = self.receipt()
        path = self.root / "receipt.json"
        path.write_bytes(receipt)
        command = [sys.executable, "-B", str(Path(__file__).with_name("review_source_binding.py")),
                   "--root", str(self.root), "--receipt", str(path)]
        result = json.loads(subprocess.check_output(command))
        self.assertTrue(result["declared_bindings_match"])
        self.assertEqual(result["target_relationship"], "same_commit")
        self.assertEqual(result["receipt_authentication"], "unverified_import")
        self.assertEqual(result["implementation_review"], "pending")
        self.assertEqual(result["reviewed_source"]["manifest_sha256"],
                         build_manifest(self.root)["manifest_sha256"])
        self.assertEqual(result["receipt_raw_sha256"], hashlib.sha256(receipt).hexdigest())

    def test_mismatch_and_absent_path_are_observed(self):
        receipt = self.receipt(source_raw_bindings={"convex/checks.ts": "0" * 64,
                                                   "missing.ts": "1" * 64})
        result = inspect_binding(self.root, receipt)
        self.assertFalse(result["declared_bindings_match"])
        self.assertEqual(result["checked_bindings"][1]["observed_sha256"], None)
        self.assertTrue(all(not item["matches"] for item in result["checked_bindings"]))

    def test_full_tree_drift_and_distinct_commit_same_tree(self):
        receipt = self.receipt()
        self.git("commit", "--allow-empty", "-qm", "same tree")
        same_tree = inspect_binding(self.root, receipt)
        self.assertEqual(same_tree["target_relationship"], "same_tree_merge")
        self.assertNotEqual(same_tree["reviewed_source"]["source_commit"],
                            same_tree["target_source"]["source_commit"])
        self.write("new-file.txt", "new input")
        self.commit()
        changed = inspect_binding(self.root, receipt)
        self.assertEqual(changed["target_relationship"], "different_tree")
        self.assertTrue(changed["declared_bindings_match"])
        self.assertEqual(changed["implementation_review"], "pending")

    def test_invalid_receipts_fail_before_git(self):
        invalid = [b'{"schema_version":1,"schema_version":1}', self.receipt(schema_version=True),
                   self.receipt(reviewed_commit="HEAD"), self.receipt(source_raw_bindings={}),
                   self.receipt(source_raw_bindings={"../bad": "0" * 64}),
                   self.receipt(source_raw_bindings={".env.local": "0" * 64}),
                   self.receipt(source_raw_bindings={"a//b": "0" * 64}),
                   self.receipt(source_raw_bindings={"a": "A" * 64})]
        with patch("review_source_binding.build_manifest") as manifest:
            for receipt in invalid:
                with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                    inspect_binding(self.root, receipt)
            manifest.assert_not_called()

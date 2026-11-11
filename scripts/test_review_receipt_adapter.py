import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from review_receipt_adapter import adapt_receipt, inspect_adapted_binding
from sidecar_digest import canonical_bytes
import test_release_manifest as fixtures


class ReviewReceiptAdapterTests(unittest.TestCase):
    setUp = fixtures.ReleaseManifestTests.setUp
    git = fixtures.ReleaseManifestTests.git
    write = fixtures.ReleaseManifestTests.write
    commit = fixtures.ReleaseManifestTests.commit

    def value(self, **changes):
        value = {"schema_version": 1, "kind": "exact_code_review", "decision": "accept",
                 "reviewed_commit": self.git("rev-parse", "HEAD").decode().strip(),
                 "source_raw_bindings": {"convex/checks.ts": hashlib.sha256(
                     b"export const scope = 'current';\n").hexdigest()},
                 "authenticated": True, "implementation_review": "accepted",
                 "reviewer": {"description": "untrusted extension"}}
        value.update(changes)
        return value

    def raw(self, **changes):
        return json.dumps(self.value(**changes), indent=2).encode() + b"\n"

    def test_type_layouts_preserve_original_digest_domain(self):
        for layout in ("kind", "artifact_kind", "both"):
            value = self.value()
            if layout != "kind": value["artifact_kind"] = "exact_code_review"
            if layout == "artifact_kind": value.pop("kind")
            raw = json.dumps(value, indent=2).encode() + b"\n"
            before = raw[:]
            metadata, normalized = adapt_receipt(raw)
            self.assertEqual(raw, before)
            self.assertEqual(metadata["receipt_raw_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(metadata["receipt_canonical_sha256"], hashlib.sha256(canonical_bytes(value)).hexdigest())
            self.assertEqual(metadata["normalized_projection_sha256"], hashlib.sha256(normalized).hexdigest())
            self.assertNotEqual(metadata["receipt_raw_sha256"], metadata["normalized_projection_sha256"])
            self.assertNotIn("reviewer", json.loads(normalized))
            self.assertNotIn("authenticated", json.loads(normalized))
            self.assertEqual(metadata["authentication"], "unverified_import")
            self.assertEqual(metadata["implementation_review"], "pending")

    def test_all_verdicts_only_compare_declared_bytes(self):
        for decision in ("accept", "revise", "unresolved"):
            result = inspect_adapted_binding(self.root, self.raw(decision=decision))
            self.assertEqual(result["declared_decision"], decision)
            self.assertEqual(result["source_binding"], "declared_git_bytes_match")
            self.assertEqual(result["coverage_completeness"], "unverified")
            self.assertEqual(result["runtime_review"], "pending")
            nested = result["projection_source_binding"]
            self.assertEqual(nested["receipt_raw_sha256"], result["normalized_projection_sha256"])
            self.assertEqual(nested["receipt_authentication"], "unverified_import")

    def test_invalid_schema_types_decisions_and_paths_before_git(self):
        invalid = [self.raw(schema_version=True), self.raw(schema_version=2),
                   self.raw(kind=None), self.raw(kind=["exact_code_review"]),
                   self.raw(artifact_kind="other"), self.raw(decision=["accept"]),
                   self.raw(decision=True), self.raw(decision="accepted"),
                   self.raw(decision=None), self.raw(reviewed_commit=["a" * 40]),
                   self.raw(reviewed_commit="HEAD"), self.raw(source_raw_bindings={}),
                   self.raw(source_raw_bindings=[])]
        for field in ("kind", "decision", "reviewed_commit", "source_raw_bindings"):
            v=self.value();v.pop(field);invalid.append(json.dumps(v).encode())
        for path in ("../bad", "/absolute", "a//b", "a/./b", ".", "a/", ".env.local",
                     "a\\b", "a\x00b", "a\nb", "x" * 513):
            invalid.append(self.raw(source_raw_bindings={path: "0" * 64}))
        for digest in (["0" * 64], True, "A" * 64, "0" * 63):
            invalid.append(self.raw(source_raw_bindings={"valid.py": digest}))
        with patch("review_receipt_adapter.inspect_binding") as binding:
            for raw in invalid:
                with self.subTest(raw=raw[:100]), self.assertRaises(ValueError):
                    inspect_adapted_binding(self.root, raw)
            binding.assert_not_called()

    def test_strict_json_bounds_duplicates_and_numbers(self):
        bad = [b'{"schema_version":1,"schema_version":1}', b'{"x":1.0}', b'{"x":NaN}',
               b'{"x":9007199254740992}', b'[]', b'\xff', b' ' * (1024 * 1024 + 1),
               self.raw(source_raw_bindings={f"f{i}.py": "0" * 64 for i in range(257)})]
        for raw in bad:
            with self.subTest(raw=raw[:100]), self.assertRaises(ValueError): adapt_receipt(raw)
        valid=self.value();valid['source_raw_bindings']={f'f{i}.py':'0'*64 for i in range(256)}
        self.assertEqual(len(adapt_receipt(json.dumps(valid).encode())[0]['declared_source_raw_bindings']),256)

    def test_absent_mismatching_files_and_target_drift_stay_separate(self):
        raw = self.raw(source_raw_bindings={"missing.py": "0" * 64, "convex/checks.ts": "1" * 64})
        result = inspect_adapted_binding(self.root, raw)
        self.assertEqual(result["source_binding"], "declared_git_bytes_mismatch")
        self.assertFalse(result["projection_source_binding"]["declared_bindings_match"])
        raw = self.raw()
        self.write("convex/checks.ts", "changed\n");self.commit()
        result=inspect_adapted_binding(self.root,raw)
        self.assertEqual(result['source_binding'],'declared_git_bytes_match')
        self.assertEqual(result['projection_source_binding']['target_relationship'],'different_tree')
        self.assertEqual(result['implementation_review'],'pending')

    def test_cli_keeps_original_file_and_does_not_create_database(self):
        path=self.root/'receipt.json';raw=self.raw();path.write_bytes(raw)
        before={p.relative_to(self.root) for p in self.root.rglob('*')}
        cli=[sys.executable,'-B',str(Path(__file__).with_name('review_receipt_adapter.py')),
             '--root',str(self.root),'--receipt',str(path)]
        result=json.loads(subprocess.check_output(cli))
        self.assertEqual(result['receipt_raw_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(path.read_bytes(),raw)
        self.assertEqual(before,{p.relative_to(self.root) for p in self.root.rglob('*')})
        path.write_bytes(b'{}');bad=subprocess.run(cli,capture_output=True)
        self.assertEqual(bad.returncode,2)
        self.assertIn(b'Receipt adaptation failed',bad.stderr)

    def test_existing_immutable_s6_artifact_adapts_without_rewrite(self):
        path=Path(__file__).resolve().parents[1]/'data/FO-W020-S6-R1-factfinder-review-v1.json'
        raw=path.read_bytes();metadata,normalized=adapt_receipt(raw)
        self.assertEqual(metadata['receipt_raw_sha256'],'14caa9cb75906bdc94dfed1bea1d19860498df9489827da6259410345370908c')
        self.assertEqual(metadata['declared_decision'],'accept')
        self.assertEqual(len(json.loads(normalized)['source_raw_bindings']),6)
        self.assertEqual(path.read_bytes(),raw)


if __name__ == '__main__': unittest.main()

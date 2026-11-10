import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from export_public_snapshot import canonical, export_public
from library_view import InvalidLibrary
from validate_pilot import record_digest

ROOT = Path(__file__).resolve().parents[1]


class PublicSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "data", self.root / "data")

    def test_checked_in_snapshot_is_reproducible_and_pins_every_record(self):
        actual = export_public(ROOT)
        self.assertEqual(actual, json.loads((ROOT / "public/library.json").read_text()))
        subject = {k: v for k, v in actual.items() if k != "snapshot_sha256"}
        self.assertEqual(hashlib.sha256(canonical(subject)).hexdigest(), actual["snapshot_sha256"])
        self.assertEqual(len(actual["records"]), 8)
        for row in actual["records"]:
            self.assertEqual(record_digest(row["record"]), row["sha256"])
            self.assertEqual(row["evidence_package"]["state"], "approved")
        abstention = next(r for r in actual["records"] if r["claim_id"] == "C003")
        self.assertEqual(abstention["evidence_package"]["answer_kind"], "reviewed_abstention")

    def test_documented_cli_reproduces_published_bytes_to_stdout_and_file(self):
        command = [sys.executable, "-B", str(ROOT / "scripts/export_public_snapshot.py")]
        expected = (ROOT / "public/library.json").read_bytes()
        stdout = subprocess.check_output(command, cwd=self.root)
        self.assertEqual(stdout, expected)
        output = self.root / "snapshot.json"
        subprocess.run(command + ["--root", str(self.root), "--output", str(output)],
                       cwd=self.root, check=True)
        self.assertEqual(output.read_bytes(), expected)

    def test_reopening_removes_answer_record_and_exact_mappings(self):
        path = self.root / "data/curation-events.json"
        data = json.loads(path.read_text())
        events = data["curation_events"]
        prior = next(e for e in reversed(events) if e["claim_id"] == "C004")
        events.append({**prior, "seq": events[-1]["seq"] + 1, "state": "reopened",
                       "at": events[-1]["at"], "reason": "Isolated export regression"})
        path.write_text(json.dumps(data))
        result = export_public(self.root)
        self.assertNotIn("C004", [r["claim_id"] for r in result["records"]])
        self.assertFalse(any(m.get("claim_id") == "C004" for m in result["exact_mappings"]))
        self.assertIn({"claim_id": "C004", "state": "reopened", "selected_version": 1}, result["withheld"])
        self.assertNotEqual(result["snapshot_sha256"], export_public(ROOT)["snapshot_sha256"])

    def test_unlisted_private_state_and_new_drafts_do_not_enter_export(self):
        for name in ["private-inbox.json", "C999-unreviewed.json"]:
            (self.root / "data" / name).write_text('{"private_fixture":"DO_NOT_EXPORT"}')
        (self.root / ".env.local").write_text("PRIVATE_FIXTURE_NOT_A_CREDENTIAL")
        self.assertEqual(export_public(self.root), export_public(ROOT))
        self.assertNotIn("DO_NOT_EXPORT", json.dumps(export_public(self.root)))

    def test_unreviewed_catalog_and_wrong_version_mapping_fail_closed(self):
        path = self.root / "data/query-catalog.json"
        catalog = json.loads(path.read_text())
        original = json.loads(path.read_text())
        catalog["routing_review_status"] = "awaiting_review"
        path.write_text(json.dumps(catalog))
        with self.assertRaises(ValueError):
            export_public(self.root)
        route = next(r for r in original["routes"] if r["kind"] == "claim")
        route["record_sha256"] = "0" * 64
        path.write_text(json.dumps(original))
        with self.assertRaises(ValueError):
            export_public(self.root)

    def test_corrupt_frozen_input_produces_no_snapshot(self):
        path = self.root / "data/C004-v1.json"
        record = json.loads(path.read_text())
        record["claim"] = "corrupt fixture"
        path.write_text(json.dumps(record))
        with self.assertRaises(InvalidLibrary):
            export_public(self.root)


if __name__ == "__main__":
    unittest.main()

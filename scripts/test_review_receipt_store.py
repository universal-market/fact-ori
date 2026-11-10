import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from review_receipt_store import MAX_BYTES, store_capture

ROOT = Path(__file__).resolve().parents[1]


class ReviewReceiptStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "captures.sqlite"
        self.receipt = b'{"schema_version":1,"decision":"accept","text":"\\u00e9"}\n'
        self.capture = {
            "schema_version": 1,
            "capture_id": "11111111-1111-4111-8111-111111111111",
            "recorded_at": "2026-11-10T11:00:00Z",
            "recorder_agent_id": "22222222-2222-4222-8222-222222222222",
            "reviewer_agent_id": "33333333-3333-4333-8333-333333333333",
            "reviewer_owner_id": None,
            "decision_post_id": "44444444-4444-4444-8444-444444444444",
            "decision_revision": 1, "reviewed_commit": "a" * 40,
            "receipt_raw_sha256": hashlib.sha256(self.receipt).hexdigest(),
            "observations": [{"tool": "get_post", "arguments": {},
                              "result_json": '{"authenticated":true,"ratio":0.5}',
                              "observed_at": "2026-11-10T11:00:00Z"}],
        }

    def store(self, capture=None, receipt=None):
        return store_capture(self.database, json.dumps(capture or self.capture).encode(),
                             self.receipt if receipt is None else receipt)

    def rows(self):
        with closing(sqlite3.connect(self.database)) as connection:
            return connection.execute("SELECT metadata, receipt_raw FROM review_captures").fetchall()

    def test_cli_preserves_raw_bytes_and_retries_without_promotion(self):
        receipt = self.root / "receipt.json"
        receipt.write_bytes(self.receipt)
        capture = self.root / "capture.json"
        capture.write_text(json.dumps(self.capture))
        command = [sys.executable, "-B", str(ROOT / "scripts/review_receipt_store.py"),
                   "--database", str(self.database), "--capture", str(capture),
                   "--receipt", str(receipt)]
        first = json.loads(subprocess.check_output(command))
        capture.write_text(json.dumps(self.capture, indent=2))
        second = json.loads(subprocess.check_output(command))
        self.assertEqual(first, second)
        self.assertEqual(first["authentication"], "unverified_import")
        self.assertEqual(first["implementation_review"], "pending")
        self.assertEqual(first["owner_relationship"], "unknown")
        self.assertEqual(self.rows()[0][1], self.receipt)
        self.assertEqual(len(self.rows()), 1)

    def test_conflicting_bytes_or_metadata_preserve_original(self):
        self.store()
        before = self.rows()
        changed = copy.deepcopy(self.capture)
        changed["recorded_at"] = "2026-11-10T11:01:00Z"
        with self.assertRaises(ValueError):
            self.store(changed)
        changed = copy.deepcopy(self.capture)
        raw = self.receipt.rstrip()
        changed["receipt_raw_sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            self.store(changed, raw)
        self.assertEqual(self.rows(), before)

    def test_concurrent_identical_retry_and_conflicting_capture(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.store(), range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(self.rows()), 1)
        changed = copy.deepcopy(self.capture)
        changed["decision_revision"] = 2
        with ThreadPoolExecutor(max_workers=2) as pool:
            good = pool.submit(self.store)
            bad = pool.submit(self.store, changed)
            self.assertEqual(good.result(), results[0])
            with self.assertRaises(ValueError):
                bad.result()
        self.assertEqual(len(self.rows()), 1)

    def test_invalid_inputs_fail_before_database_creation(self):
        variants = []
        for field, value in [("schema_version", True), ("decision_revision", True),
                             ("decision_revision", 0), ("capture_id", "handle"),
                             ("reviewed_commit", "HEAD"), ("receipt_raw_sha256", "0" * 64),
                             ("recorded_at", "2026-11-10"), ("observations", [])]:
            changed = copy.deepcopy(self.capture)
            changed[field] = value
            variants.append(json.dumps(changed).encode())
        changed = copy.deepcopy(self.capture)
        changed["authenticated"] = True
        variants.append(json.dumps(changed).encode())
        variants.extend([b'{"x":1,"x":2}', b'NaN', b'1.0', b'9007199254740992',
                         b'\xef\xbb\xbf{}', b'"\xff"', b' ' * (MAX_BYTES + 1)])
        for raw in variants:
            with self.subTest(raw=raw[:100]), self.assertRaises((ValueError, TypeError)):
                store_capture(self.database, raw, self.receipt)
            self.assertFalse(self.database.exists())

    def test_receipt_and_observation_duplicate_keys_and_tool_scope_reject(self):
        for receipt in [b'{"schema_version":1,"nested":{"x":1,"x":2}}',
                        b'{"schema_version":1,"value":NaN}', b' ' * (MAX_BYTES + 1)]:
            changed = copy.deepcopy(self.capture)
            changed["receipt_raw_sha256"] = hashlib.sha256(receipt).hexdigest()
            with self.assertRaises(ValueError):
                self.store(changed, receipt)
        for tool, result in [("complete_task", '{}'), ("get_post", '{"x":1,"x":2}'),
                             ("get_post", '{"x":NaN}'), ("get_post", '[]')]:
            changed = copy.deepcopy(self.capture)
            changed["observations"][0].update(tool=tool, result_json=result)
            with self.assertRaises(ValueError):
                self.store(changed)
        self.assertFalse(self.database.exists())

    def test_access_failure_is_preserved_as_unverified_observation(self):
        self.capture["observations"][0]["result_json"] = '{"error":"NOT_FOUND"}'
        result = self.store()
        self.assertEqual(result["capture"]["observations"], self.capture["observations"])
        self.assertEqual(result["implementation_review"], "pending")
        self.assertEqual(result["source_binding"], "unchecked")

    def test_canonical_expansion_limit_precedes_database_creation(self):
        self.capture["observations"][0]["result_json"] = json.dumps({"text": "é" * 180000},
                                                                  ensure_ascii=False)
        raw = json.dumps(self.capture, ensure_ascii=False).encode()
        self.assertLess(len(raw), MAX_BYTES)
        with self.assertRaises(ValueError):
            store_capture(self.database, raw, self.receipt)
        self.assertFalse(self.database.exists())


if __name__ == "__main__":
    unittest.main()

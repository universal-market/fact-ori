import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sidecar_digest import canonical_bytes, inspect_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/sidecar-digest-v1.json"


class SidecarDigestTests(unittest.TestCase):
    def setUp(self):
        self.vectors = json.loads(FIXTURE.read_text())["vectors"]

    def test_fixed_bytes_and_detached_hashes(self):
        for vector in self.vectors:
            with self.subTest(vector=vector["name"]):
                raw = vector["input_json"].encode("utf8")
                result = inspect_bytes(raw)
                self.assertEqual(result["canonical_json"], vector["canonical_json"])
                self.assertEqual(result["canonical_sha256"], vector["canonical_sha256"])
                self.assertEqual(result["canonical_byte_count"], len(vector["canonical_json"]))
                self.assertEqual(result["raw_sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(result["raw_byte_count"], len(raw))

    def run_cli(self, command, raw):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sidecar.json"
            path.write_bytes(raw)
            return subprocess.run([*command, str(path)], cwd=ROOT,
                                  capture_output=True, check=False)

    def test_both_normal_entry_points_match_every_vector(self):
        for vector in self.vectors:
            raw = vector["input_json"].encode("utf8")
            expected = inspect_bytes(raw)
            for command in ([sys.executable, "-B", "scripts/sidecar_digest.py"],
                            ["node", "scripts/sidecar-digest.mjs"]):
                with self.subTest(vector=vector["name"], command=command):
                    run = self.run_cli(command, raw)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(json.loads(run.stdout), expected)

    def test_invalid_or_nonportable_input_fails_both_clis(self):
        invalid = [b'1.0', b'1e0', b'1.0000000000000001', b'NaN', b'Infinity',
                   b'9007199254740992', b'-9007199254740993', b'{"a":}',
                   b'"\xff"', b'\xef\xbb\xbf{}']
        for raw in invalid:
            for command in ([sys.executable, "-B", "scripts/sidecar_digest.py"],
                            ["node", "scripts/sidecar-digest.mjs"]):
                with self.subTest(raw=raw, command=command):
                    run = self.run_cli(command, raw)
                    self.assertEqual(run.returncode, 2)
                    self.assertEqual(run.stdout, b"")

    def test_all_fields_included_and_raw_format_separate(self):
        first = inspect_bytes(b'{"sha256":"claimed", "supersedes":{"hash":"old"}}\n')
        reformatted = inspect_bytes(b'{"supersedes":{"hash":"old"},"sha256":"claimed"}')
        self.assertEqual(first["canonical_sha256"], reformatted["canonical_sha256"])
        self.assertNotEqual(first["raw_sha256"], reformatted["raw_sha256"])
        changed = inspect_bytes(b'{"sha256":"changed", "supersedes":{"hash":"old"}}\n')
        self.assertNotEqual(first["canonical_sha256"], changed["canonical_sha256"])
        changed_reference = inspect_bytes(b'{"sha256":"claimed", "supersedes":{"hash":"new"}}\n')
        self.assertNotEqual(first["canonical_sha256"], changed_reference["canonical_sha256"])
        self.assertNotEqual(canonical_bytes("é"), canonical_bytes("e\u0301"))

    def test_python_rejects_unsupported_runtime_values(self):
        for value in [1.0, float("nan"), 2**53, {1: "key"}, (1,), {"bad": object()}]:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                canonical_bytes(value)

    def test_javascript_rejects_unsupported_runtime_values(self):
        source = '''
import { canonicalJson } from "./scripts/sidecar-digest.mjs";
const hidden = Object.defineProperty({}, "hidden", {value: 1});
for (const value of [undefined, NaN, Infinity, 1.5, 2**53, 1n, new Date(),
                     [undefined], new Array(1), {bad: undefined}, {[Symbol()]: 1}, hidden]) {
  let rejected = false;
  try { canonicalJson(value); } catch { rejected = true; }
  if (!rejected) throw new Error("Unsupported runtime value was accepted");
}
'''
        run = subprocess.run(["node", "--input-type=module", "-"], cwd=ROOT,
                             input=source, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)

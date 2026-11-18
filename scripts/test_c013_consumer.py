"""Exercise the C013 offline consumer and its separation from active exports."""

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from ask import lookup
from c013_consumer import EVENTS_PATH, RECORD_PATH, SCOPE_PATH, lookup_recording
from export_api_seed import build_snapshot
from export_public_snapshot import export_public
from library_view import load_view

ROOT = Path(__file__).resolve().parents[1]


class C013ConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = (ROOT / SCOPE_PATH).read_bytes()
        cls.inputs = {
            path: (ROOT / path).read_bytes()
            for path in json.loads(cls.scope)["baseline_pins"]
        }
        cls.event = json.loads(cls.inputs[EVENTS_PATH])[-1]
        cls.record = json.loads(cls.inputs[RECORD_PATH])
        spec = importlib.util.spec_from_file_location(
            "reviewed_c013_preview", ROOT / "data/C013-routing-implementation-v2/route.py"
        )
        cls.preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.preview)

    def resolve(self, question, inputs=None, objections=None):
        return lookup_recording(
            question, self.scope, self.inputs if inputs is None else inputs,
            unresolved_objections=[] if objections is None else objections,
        )

    def test_reviewed_literals_and_unreviewed_variants(self):
        self.assertEqual(len(self.preview.ROUTES), 7)
        for question, (classification, _) in self.preview.ROUTES.items():
            with self.subTest(question=question):
                result = self.resolve(question)
                self.assertEqual(result["classification"], classification)
                self.assertIsNone(result["answer"])
                self.assertFalse(result["release_authorized"])
                self.assertFalse(result["active_import_authorized"])
                self.assertNotIn("proposed_response_after_remaining_gates", result)
                for variant in (question.upper(), " " + question, question + "?",
                                question.replace("'", "’")):
                    if variant != question:
                        self.assertEqual(self.resolve(variant)["classification"], "unmapped")

    def test_provenance_is_detached(self):
        result = self.resolve("Can lightning strike the same place twice?")
        for actual, expected in (
            ("scope", "record_scope"),
            ("excluded_scopes", "excluded_scopes"),
            ("current_limitations", "current_limitations"),
            ("historical_draft_metadata", "historical_draft_metadata"),
            ("decision_conditions", "conditions"),
            ("source_dependence", "source_dependence"),
            ("eligibility_decision_actor", "actor"),
            ("event_recorder", "recorded_by"),
        ):
            self.assertEqual(result[actual], self.event[expected])
        self.assertEqual(result["inference"], self.record["inference"])
        self.assertEqual(result["record_author"], self.record["author"])
        expected = copy.deepcopy(result)
        result["excluded_scopes"].clear()
        result["roles_and_dependence"].clear()
        result["input_raw_sha256"].clear()
        self.assertEqual(self.resolve(result["query"]), expected)

    def test_fail_closed_on_input_changes_and_objections(self):
        question = "Can lightning strike the same place twice?"
        for path in self.inputs:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.resolve(question, self.inputs | {path: self.inputs[path] + b" "})
        with self.assertRaises(ValueError):
            self.resolve(question, {p: b for p, b in self.inputs.items() if p != EVENTS_PATH})
        for field, value in (("post_revision", 2), ("conditions", []),
                             ("release_authorized", True), ("active_import_authorized", True)):
            events = json.loads(self.inputs[EVENTS_PATH])
            events[-1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.resolve(question, self.inputs | {EVENTS_PATH: json.dumps(events).encode()})
        old_view = ROOT / "data/C013-reviewed-pending-view-v1.json"
        with self.assertRaises(ValueError):
            self.resolve(question, self.inputs | {"data/C013-reviewed-pending-view-v2.json": old_view.read_bytes()})
        with self.assertRaises(ValueError):
            lookup_recording(question, self.scope + b" ", self.inputs, unresolved_objections=[])
        for objections in (["awaiting correction"], (), False):
            with self.subTest(objections=objections), self.assertRaises(ValueError):
                self.resolve(question, objections=objections)

    def test_existing_consumers_unchanged_by_diagnostic(self):
        catalog = json.loads(self.inputs["data/query-catalog.json"])
        view = load_view(ROOT)
        questions = [q for route in catalog["routes"] for q in route["questions"]]
        answers = [lookup(q, view, catalog) for q in questions]
        snapshots = build_snapshot(ROOT), export_public(ROOT)
        for question in self.preview.ROUTES:
            self.resolve(question)
            self.assertEqual(lookup(question, view, catalog)["status"], "not_in_library")
        self.assertEqual([lookup(q, load_view(ROOT), catalog) for q in questions], answers)
        self.assertEqual((build_snapshot(ROOT), export_public(ROOT)), snapshots)
        self.assertNotIn("C013", json.dumps(snapshots))

    def test_cli_requires_explicit_objection_observation(self):
        cmd = [sys.executable, "-B", str(ROOT / "scripts/c013_consumer.py"),
               "Can lightning strike the same place twice?"]
        missing = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(missing.returncode, 0)
        done = subprocess.run(cmd + ["--no-known-objections"], capture_output=True, text=True, check=True)
        self.assertIsNone(json.loads(done.stdout)["answer"])


if __name__ == "__main__":
    unittest.main()

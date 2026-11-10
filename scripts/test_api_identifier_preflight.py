"""Public exports cannot publish task-local or otherwise unaddressable IDs."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from export_api_seed import build_snapshot, require_api_claim_id
from export_public_snapshot import export_public


class ApiIdentifierPreflightTests(unittest.TestCase):
    def test_public_identifier_domain(self):
        for claim_id in ["C004", "C007a", "C13", "C0"]:
            require_api_claim_id(claim_id)
        for claim_id in ["W026-A", "C004AA", "c004", "C004\n", "C٤", "", None]:
            with self.subTest(claim_id=claim_id), self.assertRaisesRegex(ValueError, "C-number"):
                require_api_claim_id(claim_id)

    def test_both_public_exports_reject_unselected_task_local_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            (data / "library-inputs.json").write_text(json.dumps({"bundles": ["candidate.json"]}))
            (data / "query-catalog.json").write_text(json.dumps({
                "routing_review_status": "reviewed", "routes": []}))
            (data / "candidate.json").write_text(json.dumps({
                "records": [{"id": "W026-A", "version": 1}], "reviews": []}))
            # Schema/lifecycle acceptance alone does not establish API compatibility.
            with patch("export_api_seed.load_view", return_value={"claims": []}):
                for export in [build_snapshot, export_public]:
                    with self.subTest(export=export.__name__), self.assertRaisesRegex(ValueError, "W026-A"):
                        export(root)

    def test_claim_routes_are_checked_even_without_selected_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            (data / "library-inputs.json").write_text(json.dumps({"bundles": []}))
            (data / "query-catalog.json").write_text(json.dumps({
                "routing_review_status": "reviewed",
                "routes": [{"kind": "claim", "claim_id": "W026-A"}]}))
            with patch("export_api_seed.load_view", return_value={"claims": []}):
                with self.assertRaisesRegex(ValueError, "W026-A"):
                    build_snapshot(root)


if __name__ == "__main__":
    unittest.main()

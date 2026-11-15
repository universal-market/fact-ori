import copy
import unittest

from market_checkpoint_diff import compare


AGENT = "e94a196f-fcdb-4a14-b6e6-e02d50abe5d3"
OWNER = "167fdd40-59f0-49d1-a287-ac76a0998090"
LISTING = "8213ad0c-b7e6-4a26-bd82-e76c9f07f081"
TX = "6d23cb95-5dbd-4332-8f0d-c327def3fde1"


def capture():
    return {"schema_version": 1, "observed_at": "2026-11-15T16:00:00Z",
            "actor": {"agent_id": AGENT, "owner_id": OWNER},
            "listings": {"count": 1, "next_cursor": None, "observed": [
                {"id": LISTING, "status": "active", "updated_at": "2026-11-15T15:00:00Z"}]},
            "transactions": {"count": 1, "next_cursor": None, "observed": [
                {"id": TX, "state": "fulfilling", "result": None, "contract_id": None,
                 "execution_id": None, "updated_at": "2026-11-15T15:00:00Z"}]}}


class CheckpointDiffTests(unittest.TestCase):
    def test_unchanged_is_only_summary_observation(self):
        result = compare(capture(), capture())
        self.assertEqual(result["coverage"], "local_summary_columns_only")
        self.assertEqual(result["collections"]["transactions"]["changed"], [])
        self.assertIn("not authenticated remote receipts", result["limits"])
        self.assertIn("Tasks still require ordinary remote reads", result["limits"])

    def test_state_and_result_change_does_not_create_approval(self):
        before = capture()
        after = copy.deepcopy(before)
        after["transactions"]["observed"][0].update(state="closed", result="complete")
        row = compare(before, after)["collections"]["transactions"]["changed"][0]
        self.assertEqual(row["columns"]["state"], {"before": "fulfilling", "after": "closed"})
        self.assertEqual(row["columns"]["result"]["after"], "complete")
        self.assertNotIn("accepted", row)

    def test_partial_page_never_calls_missing_row_deleted(self):
        before = capture()
        after = capture()
        after["listings"] = {"count": 0, "next_cursor": "continuation", "observed": []}
        row = compare(before, after)["collections"]["listings"]
        self.assertEqual(row["not_observed_in_after_ids"], [LISTING])
        self.assertFalse(row["both_captures_declare_no_next_page"])
        self.assertNotIn("deleted", row)

    def test_newly_observed_not_claimed_newly_created(self):
        before = capture()
        before["listings"] = {"count": 0, "next_cursor": "earlier-page", "observed": []}
        row = compare(before, capture())["collections"]["listings"]
        self.assertEqual(row["newly_observed_ids"], [LISTING])
        self.assertFalse(row["both_captures_declare_no_next_page"])

    def test_identity_and_time_mismatches_reject(self):
        for key in ("agent_id", "owner_id"):
            after = capture()
            after["actor"][key] = LISTING
            with self.assertRaisesRegex(ValueError, "mismatch"):
                compare(capture(), after)
        after = capture()
        after["observed_at"] = "2026-11-14T16:00:00Z"
        with self.assertRaisesRegex(ValueError, "predates"):
            compare(capture(), after)

    def test_ambiguous_or_incomplete_capture_rejects(self):
        mutations = [
            lambda c: c["listings"].pop("next_cursor"),
            lambda c: c["listings"].update(count=True),
            lambda c: c["listings"].update(count=2),
            lambda c: c["listings"]["observed"][0].update(unknown="ignored?"),
            lambda c: c["listings"]["observed"][0].update(status="accepted"),
            lambda c: c["transactions"]["observed"][0].update(result="approved"),
            lambda c: c.update(observed_at="2026-11-15T16:00:00"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                after = capture()
                mutate(after)
                with self.assertRaises((ValueError, TypeError)):
                    compare(capture(), after)

    def test_duplicate_ids_and_invalid_uuid_reject(self):
        after = capture()
        after["listings"]["observed"] *= 2
        after["listings"]["count"] = 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compare(capture(), after)
        after = capture()
        after["transactions"]["observed"][0]["id"] = "not-an-id"
        with self.assertRaises(ValueError):
            compare(capture(), after)

    def test_inputs_are_not_mutated(self):
        before, after = capture(), capture()
        original = copy.deepcopy((before, after))
        compare(before, after)
        self.assertEqual((before, after), original)


if __name__ == "__main__":
    unittest.main()

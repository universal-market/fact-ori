"""Exercise C013 consent admission in disposable databases only."""

import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier

from c013_consent_admission import admit, advance_epoch, initialize


class ConsentAdmissionTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.db = Path(directory) / "consent.sqlite"
        initialize(self.db)
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("CREATE TABLE audit (target TEXT, operation TEXT)")
            for table in ("intake_keys", "outbox"):
                for operation in ("INSERT", "UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER audit_{table}_{operation} "
                        f"AFTER {operation} ON {table} BEGIN "
                        f"INSERT INTO audit VALUES ('{table}', '{operation}'); END"
                    )

    def request(self, **changes):
        base = dict(
            route="unmapped",
            scope="fixture-client",
            request_key="fixture-request",
            payload="Disposable inquiry",
            expected_epoch=1,
        )
        return admit(self.db, **(base | changes))

    def state(self):
        with closing(sqlite3.connect(self.db)) as connection:
            writes = connection.execute(
                "SELECT target, operation FROM audit ORDER BY rowid"
            ).fetchall()
            keys = connection.execute(
                "SELECT scope, request_key, payload, epoch, job_id FROM intake_keys"
            ).fetchall()
            jobs = connection.execute("SELECT job_id, payload, epoch FROM outbox").fetchall()
        return writes, keys, jobs

    def assert_no_effect(self, status, **changes):
        before = self.state()
        self.assertEqual(self.request(**changes), {"status": status})
        self.assertEqual(self.state(), before)

    def test_non_intake_routes_ignore_true(self):
        for route, status in (
            ("preview", "preview"),
            ("blocked_literal", "withheld"),
            ("mapped_literal", "mapped"),
        ):
            with self.subTest(route=route):
                self.assert_no_effect(status, route=route, public_review=True)
        self.assertEqual(self.state(), ([], [], []))

    def test_absent_false_and_invalid_do_not_write(self):
        self.assert_no_effect("no_consent")
        self.assert_no_effect("no_consent", public_review=False)
        for value in (None, "true", 1, 0, [], {}):
            with self.subTest(value=value):
                self.assert_no_effect("invalid_consent", public_review=value)
        self.assertEqual(self.state(), ([], [], []))

    def assert_one_job(self, job_id):
        writes, keys, jobs = self.state()
        self.assertEqual(
            writes, [("outbox", "INSERT"), ("intake_keys", "INSERT")]
        )
        self.assertEqual(
            keys, [("fixture-client", "fixture-request", "Disposable inquiry", 1, job_id)]
        )
        self.assertEqual(jobs, [(job_id, "Disposable inquiry", 1)])

    def test_true_binds_one_job_and_identical_replay_does_not_write(self):
        result = self.request(public_review=True)
        self.assertEqual(result["status"], "queued")
        self.assert_one_job(result["job_id"])
        self.assertEqual(self.request(public_review=True), result)
        self.assert_one_job(result["job_id"])

    def test_concurrent_identical_requests_share_one_job(self):
        ready = Barrier(2, timeout=5)

        def concurrent_request():
            ready.wait()
            return self.request(public_review=True)

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(concurrent_request)
            second = executor.submit(concurrent_request)
            result = first.result(timeout=10)
            self.assertEqual(second.result(timeout=10), result)
        self.assertEqual(result["status"], "queued")
        self.assert_one_job(result["job_id"])

    def test_current_key_conflicts_on_exact_payload_or_consent_change(self):
        self.request(public_review=True)
        self.assert_no_effect("conflict", payload="Disposable inquiry ", public_review=True)
        self.assert_no_effect("conflict", public_review=False)
        self.assert_no_effect("conflict")

    def test_revoked_epoch_before_transaction_does_not_write(self):
        self.assertTrue(advance_epoch(self.db, expected=1, replacement=2))
        self.assertFalse(advance_epoch(self.db, expected=1, replacement=3))
        with self.assertRaises(ValueError):
            advance_epoch(self.db, expected=2, replacement=1)
        self.assert_no_effect("stale", expected_epoch=1, public_review=True)
        self.assertEqual(self.state(), ([], [], []))

    def test_expired_binding_is_stale_before_payload_or_consent_comparison(self):
        original = self.request(public_review=True)
        self.assertTrue(advance_epoch(self.db, expected=1, replacement=2))
        for changes in (
            {"public_review": True},
            {"public_review": True, "payload": "Changed inquiry"},
            {"public_review": False, "payload": "Changed inquiry"},
            {"payload": "Changed inquiry"},
        ):
            with self.subTest(changes=changes):
                self.assert_no_effect("stale", expected_epoch=2, **changes)
        self.assert_no_effect("stale", expected_epoch=1, public_review=True)
        self.assert_one_job(original["job_id"])

    def test_missing_or_failed_transaction_has_no_committed_effect(self):
        self.assert_no_effect("unavailable", public_review=True, expected_epoch=None)
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute(
                "CREATE TRIGGER fail_binding BEFORE INSERT ON intake_keys "
                "BEGIN SELECT RAISE(ABORT, 'fixture write failure'); END"
            )
        self.assert_no_effect("unavailable", public_review=True)
        self.assertEqual(self.state(), ([], [], []))


if __name__ == "__main__":
    unittest.main()

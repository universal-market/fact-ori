"""Isolated C013 consent-admission model backed by a disposable SQLite file.

The caller supplies the routing outcome and its expected serving epoch.
This module does not select routes, publish evidence, or connect to the API.
"""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


_ABSENT = object()
_NON_INTAKE = {
    "preview": "preview",
    "blocked_literal": "withheld",
    "mapped_literal": "mapped",
}


@contextmanager
def _transaction(path, *, create=False):
    uri = Path(path).resolve().as_uri() + ("?mode=rwc" if create else "?mode=rw")
    with closing(sqlite3.connect(uri, uri=True)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        yield connection


def initialize(path):
    """Initialize a fresh fixture with epoch 1."""
    with _transaction(path, create=True) as connection:
        connection.execute(
            "CREATE TABLE serving_epoch (singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
            "epoch INTEGER NOT NULL CHECK(epoch > 0))"
        )
        connection.execute("INSERT INTO serving_epoch VALUES (1, 1)")
        connection.execute(
            "CREATE TABLE outbox (job_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, "
            "epoch INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE intake_keys (scope TEXT NOT NULL, request_key TEXT NOT NULL, "
            "payload TEXT NOT NULL, epoch INTEGER NOT NULL, job_id INTEGER NOT NULL UNIQUE "
            "REFERENCES outbox(job_id), PRIMARY KEY (scope, request_key))"
        )


def _valid_epoch(value):
    return type(value) is int and 0 < value < 2**63


def advance_epoch(path, expected, replacement):
    """Advance the fixture epoch using a non-reusable compare-and-set."""
    if not _valid_epoch(expected) or not _valid_epoch(replacement) or replacement <= expected:
        raise ValueError("replacement epoch must be strictly greater than the expected epoch")
    with _transaction(path) as connection:
        return connection.execute(
            "UPDATE serving_epoch SET epoch = ? WHERE singleton = 1 AND epoch = ?",
            (replacement, expected),
        ).rowcount == 1


def admit(path, *, route, scope, request_key, payload, expected_epoch, public_review=_ABSENT):
    """Model the v3 consent decision at the database transaction boundary.

    A persisted binding always represents explicitly supplied Boolean true.
    The same transaction checks the epoch and the key and writes both rows.
    A later response layer must validate its epoch again before disclosure.
    """
    if public_review is not _ABSENT and type(public_review) is not bool:
        return {"status": "invalid_consent"}
    if type(route) is not str:
        return {"status": "invalid_request"}
    if route in _NON_INTAKE:
        return {"status": _NON_INTAKE[route]}
    if route != "unmapped" or not all(
        type(value) is str and value.strip() for value in (scope, request_key, payload)
    ):
        return {"status": "invalid_request"}
    if not _valid_epoch(expected_epoch):
        return {"status": "unavailable"}

    try:
        with _transaction(path) as connection:
            row = connection.execute(
                "SELECT epoch FROM serving_epoch WHERE singleton = 1"
            ).fetchone()
            if row is None:
                return {"status": "unavailable"}
            current_epoch = row[0]
            if current_epoch != expected_epoch:
                return {"status": "stale"}

            binding = connection.execute(
                "SELECT payload, epoch, job_id FROM intake_keys "
                "WHERE scope = ? AND request_key = ?",
                (scope, request_key),
            ).fetchone()
            if binding is not None:
                prior_payload, prior_epoch, job_id = binding
                if prior_epoch != current_epoch:
                    return {"status": "stale"}
                if prior_payload != payload or public_review is not True:
                    return {"status": "conflict"}
                return {"status": "queued", "job_id": job_id}
            if public_review is not True:
                return {"status": "no_consent"}

            job_id = connection.execute(
                "INSERT INTO outbox (payload, epoch) VALUES (?, ?)", (payload, current_epoch)
            ).lastrowid
            connection.execute(
                "INSERT INTO intake_keys (scope, request_key, payload, epoch, job_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (scope, request_key, payload, current_epoch, job_id),
            )
            return {"status": "queued", "job_id": job_id}
    except sqlite3.DatabaseError:
        return {"status": "unavailable"}

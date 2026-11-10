"""Detached synthetic collector probes plus real isolated journal storage."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
from review_receipt_store import store_capture

script = Path(__file__).with_suffix('.mjs')
p = subprocess.run(['node', str(script), str(root)], capture_output=True, text=True, timeout=30, check=True)
report = json.loads(p.stdout)
capture = json.dumps(report.pop('journalCases')[0]).encode()
receipt = report.pop('receipt').encode()
with tempfile.TemporaryDirectory(prefix='factfinder-S3-R2-') as tmp:
    database = Path(tmp) / 'review.sqlite'
    first = store_capture(database, capture, receipt)
    second = store_capture(database, capture, receipt)
    assert first == second
    report['passed'].append('valid synthetic capture stores and identical retry is idempotent')
    assert first['authentication'] == 'unverified_import'
    assert first['implementation_review'] == 'pending'
    assert first['source_binding'] == 'unchecked'
    assert first['owner_relationship'] == 'unknown'
    report['passed'].append('journal retains unverified/pending/unchecked/unknown metadata')
    with sqlite3.connect(database) as db:
        rows = db.execute('SELECT receipt_raw FROM review_captures').fetchall()
    assert rows == [(receipt,)]
    assert first['receipt_raw_sha256'] == hashlib.sha256(receipt).hexdigest()
    report['passed'].append('one stored row preserves exact original synthetic receipt bytes')
report['assertion_count'] = len(report['passed'])
print(json.dumps(report, indent=2))

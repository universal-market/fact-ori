"""Run detached Node probes and strict journal checks without authenticated reads."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
from review_receipt_store import capture_metadata

script = Path(__file__).with_suffix('.mjs')
p = subprocess.run(['node', str(script), str(root)], capture_output=True, text=True, timeout=30, check=True)
report = json.loads(p.stdout)
cases = report.pop('journalCases')
receipt = report.pop('receipt').encode()
normal = capture_metadata(json.dumps(cases[0]).encode(), receipt)
assert normal['authentication'] == 'unverified_import'
assert normal['implementation_review'] == 'pending'
assert normal['source_binding'] == 'unchecked'
report['passed'].append('normal collector packet accepted by strict journal without promotion')
for label, capture in zip(['array commit', 'array digest', 'array owner'], cases[1:], strict=True):
    try:
        capture_metadata(json.dumps(capture).encode(), receipt)
    except (ValueError, TypeError):
        report['passed'].append('strict journal rejects ' + label)
    else:
        raise AssertionError(label)
report['assertion_count'] = len(report['passed'])
print(json.dumps(report, indent=2))

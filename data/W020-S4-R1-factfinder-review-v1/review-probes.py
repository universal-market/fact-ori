"""Run synthetic frontier assertions and confirm separate S1 schema boundary."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
from review_receipt_store import capture_metadata

p = subprocess.run(['node', str(Path(__file__).with_suffix('.mjs')), str(root)], capture_output=True, text=True, timeout=30, check=True)
report = json.loads(p.stdout)
envelope = report.pop('normal_envelope')
try:
    capture_metadata(json.dumps(envelope).encode(), b'{"schema_version":1}')
except ValueError as error:
    assert str(error) == 'Unsupported capture fields'
    report['passed'].append('separate frontier envelope rejected by S1 capture schema')
else:
    raise AssertionError('Frontier envelope unexpectedly accepted by S1')
report['assertion_count'] = len(report['passed'])
print(json.dumps(report, indent=2))

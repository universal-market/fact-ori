import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'scripts'))
from export_public_snapshot import canonical, export_public
from validate_pilot import record_digest

checks=[]
def check(name,passed,detail=None):
    assert passed,(name,detail)
    checks.append({'name':name,'pass':passed,'detail':detail})
script=root/'scripts/export_public_snapshot.py'
expected=(root/'public/library.json').read_bytes()
before=export_public(root)
cmd=[sys.executable,'-B',str(script)]
with tempfile.TemporaryDirectory() as td:
    temp=Path(td)
    stdout=subprocess.check_output(cmd,cwd=temp)
    check('default-root-stdout-bytes',stdout==expected,hashlib.sha256(stdout).hexdigest())
    dest=temp/'nested/snapshot.json'
    done=subprocess.run(cmd+['--root',str(root),'--output',str(dest)],cwd=temp,capture_output=True,check=True)
    check('explicit-root-file-bytes',dest.read_bytes()==expected)
    check('output-path-no-stdout',done.stdout==b'')
    # A distinct root must actually affect output, rather than both options
    # accidentally reading the checkout root containing identical copied data.
    other=temp/'other';shutil.copytree(root/'data',other/'data')
    p=other/'data/curation-events.json';events=json.loads(p.read_text())
    events['curation_events'][-1]['reason']+=' (isolated reviewer fixture)'
    p.write_text(json.dumps(events))
    alternate=export_public(other)
    alt=subprocess.check_output(cmd+['--root',str(other)],cwd=temp)
    check('changed-explicit-root-observed',json.loads(alt)==alternate and alt!=expected)
    check('changed-root-curation-digest',alternate['curation_log_sha256']!=before['curation_log_sha256'])

    # Run the newly introduced exact regression against a detached mutation
    # restoring ONLY the old ensure_ascii=False implementation line.
    mutant=temp/'mutant';mutant.mkdir()
    for name in ['scripts','data','public','tests']:
        shutil.copytree(root/name,mutant/name)
    target=mutant/'scripts/export_public_snapshot.py'
    source=target.read_text();needle='json.dumps(export_public(args.root), indent=2, ensure_ascii=True)'
    assert source.count(needle)==1
    target.write_text(source.replace(needle,needle.replace('True','False')))
    failed=subprocess.run([sys.executable,'-B','-m','unittest',
        'test_public_snapshot.PublicSnapshotTests.test_documented_cli_reproduces_published_bytes_to_stdout_and_file'],
        cwd=mutant/'scripts',capture_output=True,text=True)
    check('new-regression-kills-prior-serialization',failed.returncode==1 and 'AssertionError' in failed.stderr,
          {'exit_code':failed.returncode,'assertion_failure':True})

obj=json.loads(stdout)
check('snapshot-object-unchanged',obj==before)
subject={k:v for k,v in obj.items() if k!='snapshot_sha256'}
check('canonical-snapshot-digest-preserved',hashlib.sha256(canonical(subject)).hexdigest()==obj['snapshot_sha256'])
check('all-eight-record-identities-preserved',len(obj['records'])==8 and all(record_digest(x['record'])==x['sha256'] for x in obj['records']))
check('ascii-transport-with-terminal-lf',all(x<128 for x in stdout) and stdout.endswith(b'\n') and not stdout.endswith(b'\n\n'))

# Exercise main's serializer with a synthetic return object; this tests escaping
# only, not validation/eligibility of these strings as factual library records.
ns=runpy.run_path(str(script),run_name='review_only')
vectors=['é','e\u0301','😀','\u2028\u2029','quote" slash\\ newline\n tab\t nul\x00','<tag>&']
with patch.dict(ns['main'].__globals__,{'export_public':lambda _: {'vectors':vectors}}),patch.object(sys,'argv',[str(script)]):
    out=io.StringIO()
    with contextlib.redirect_stdout(out): ns['main']()
    encoded=out.getvalue()
check('synthetic-unicode-control-roundtrip',json.loads(encoded)=={'vectors':vectors} and encoded.isascii())
check('no-unicode-normalization',json.loads(encoded)['vectors'][0]!=json.loads(encoded)['vectors'][1])

print(json.dumps({'reviewed_commit':'8adcfa9d8c1dcca7d65d7d3c3cce19795e09b0bf','checks_passed':len(checks),'checks':checks,
 'limits':['Linux/Python execution only; Windows newline translation and alternate locale/platform behavior untested.',
 'Synthetic serialization vectors do not establish factual record validity or source truth.',
 'CLI byte representation is Python json indent2/ASCII escapes/LF on this environment, not JCS or deployment attestation.']},indent=2))

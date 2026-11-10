import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'scripts'))
from review_receipt_store import MAX_BYTES, capture_metadata, store_capture
from sidecar_digest import canonical_bytes

receipt=b'{"schema_version":1,"decision":"accept","text":"\\u00e9"}\n'
base={'schema_version':1,'capture_id':'11111111-1111-4111-8111-111111111111',
 'recorded_at':'2026-11-10T12:00:00Z','recorder_agent_id':'22222222-2222-4222-8222-222222222222',
 'reviewer_agent_id':'33333333-3333-4333-8333-333333333333','reviewer_owner_id':None,
 'decision_post_id':'44444444-4444-4444-8444-444444444444','decision_revision':1,
 'reviewed_commit':'a'*40,'receipt_raw_sha256':hashlib.sha256(receipt).hexdigest(),
 'observations':[{'tool':'get_post','arguments':{},'result_json':'{"authenticated":true,"ratio":0.5}',
 'observed_at':'2026-11-10T12:00:00Z'}]}
checks=[]
def check(name,passed):
 assert passed,name
 checks.append({'name':name,'pass':True})
def raw(c):return json.dumps(c,ensure_ascii=False).encode()
variants=[]
for k,v in [('schema_version',True),('capture_id','factfinder'),('reviewer_agent_id','ABC'),
 ('reviewer_owner_id',1),('decision_revision',True),('decision_revision',0),
 ('decision_revision',2**53),('recorded_at','2026-11-10'),('reviewed_commit','HEAD'),
 ('reviewed_commit','A'*40),('observations',[]),('receipt_raw_sha256','0'*64)]:
 c=copy.deepcopy(base);c[k]=v;variants.append((k+repr(v),raw(c),receipt))
for tool,result in [('poll_events','{}'),('get_post','[]'),('get_post','{"x":1,"x":2}'),('get_post','{"x":NaN}')]:
 c=copy.deepcopy(base);c['observations'][0].update(tool=tool,result_json=result)
 variants.append(('observation:'+tool+result,raw(c),receipt))
for value in [b'{"schema_version":1,"schema_version":1}',b'{"schema_version":1,"nested":{"x":1,"x":2}}',
 b'{"schema_version":1,"x":1.0}',b'{"schema_version":1,"x":9007199254740992}',b'\xef\xbb\xbf{}',b'"\xff"',b' '*(MAX_BYTES+1)]:
 c=copy.deepcopy(base);c['receipt_raw_sha256']=hashlib.sha256(value).hexdigest()
 variants.append(('invalid-receipt:'+str(len(variants)),raw(c),value))
c=copy.deepcopy(base);c['observations'][0]['result_json']=json.dumps({'text':'é'*180000},ensure_ascii=False)
variants.append(('canonical-expansion-limit',raw(c),receipt))
with tempfile.TemporaryDirectory() as td:
 p=Path(td)
 for i,(name,c,r) in enumerate(variants):
  db=p/f'invalid-{i}.sqlite'
  try:store_capture(db,c,r);rejected=False
  except (ValueError,TypeError,RecursionError):rejected=True
  check('reject-before-db:'+name,rejected and not db.exists())
 db=p/'journal.sqlite';m=store_capture(db,raw(base),receipt)
 check('fixed-unverified-statuses',all(m[k]==v for k,v in {'authentication':'unverified_import','owner_relationship':'unknown','source_binding':'unchecked','implementation_review':'pending'}.items()))
 check('claim-authenticated-does-not-promote',json.loads(m['capture']['observations'][0]['result_json'])['authenticated'] is True and m['authentication']=='unverified_import')
 retry=store_capture(db,json.dumps(base,indent=4).encode(),receipt)
 check('capture-whitespace-canonical-retry',retry==m)
 with sqlite3.connect(db) as con: original=con.execute('SELECT metadata,receipt_raw FROM review_captures').fetchall()
 check('raw-receipt-and-canonical-metadata-retained',original==[(canonical_bytes(m),receipt)])
 c=copy.deepcopy(base);c['recorded_at']='2026-11-10T12:00:01Z'
 try:store_capture(db,raw(c),receipt);failed=False
 except ValueError:failed=True
 with sqlite3.connect(db) as con:after=con.execute('SELECT metadata,receipt_raw FROM review_captures').fetchall()
 check('conflicting-retry-preserves-row',failed and after==original)
 # Equivalent receipt JSON can share canonical digest but raw bytes/UUID stay separate.
 c=copy.deepcopy(base);c['capture_id']='55555555-5555-4555-8555-555555555555'
 other=b'{ "text":"\xc3\xa9", "decision":"accept", "schema_version":1 }'
 c['receipt_raw_sha256']=hashlib.sha256(other).hexdigest();n=store_capture(db,raw(c),other)
 check('raw-versus-canonical-domain',n['receipt_canonical_sha256']==m['receipt_canonical_sha256'] and n['receipt_raw_sha256']!=m['receipt_raw_sha256'])
 c=copy.deepcopy(base);c['observations'][0]['result_json']='{"error":"NOT_FOUND","visibility":"unknown"}'
 n=capture_metadata(raw(c),receipt)
 check('access-error-preserved-without-cause-inference',n['capture']['observations']==c['observations'] and n['implementation_review']=='pending')
 rp=p/'receipt.json';rp.write_bytes(receipt);cp=p/'capture.json';cp.write_bytes(raw(base))
 cmd=[sys.executable,'-B',str(root/'scripts/review_receipt_store.py'),'--database',str(p/'process.sqlite'),'--capture',str(cp),'--receipt',str(rp)]
 processes=[subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(4)]
 output=[x.communicate(timeout=10) for x in processes]
 check('four-process-identical-cli-retry',all(x.returncode==0 for x in processes) and all(json.loads(x[0])==json.loads(output[0][0]) for x in output))
 with sqlite3.connect(p/'process.sqlite') as con:count=con.execute('SELECT count(*) FROM review_captures').fetchone()[0]
 check('concurrent-cli-exactly-one-row',count==1)
 # Locked database must fail within bounded subprocess deadline, preserving original.
 c=copy.deepcopy(base);c['capture_id']='66666666-6666-4666-8666-666666666666';cp.write_bytes(raw(c))
 with sqlite3.connect(p/'process.sqlite') as con:
  con.execute('BEGIN IMMEDIATE')
  locked=subprocess.run(cmd,capture_output=True,timeout=9)
  con.rollback()
 check('sqlite-lock-timeout-cli-error',locked.returncode==2 and locked.stdout==b'' and b'locked' in locked.stderr)
 with sqlite3.connect(p/'process.sqlite') as con:count=con.execute('SELECT count(*) FROM review_captures').fetchone()[0]
 check('lock-failure-no-partial-row',count==1)
print(json.dumps({'reviewed_commit':'55d4b8bddf7c8c9cc0f879b412d69f933e116a37','checks_passed':len(checks),'checks':checks,
 'limits':['Caller capture declarations are unverified; no live authenticated acquisition or lifecycle/source/runtime verification.',
 'SQLite operator-controlled file is not cryptographically append-only or tamper-proof; concurrency exercised on local filesystem only.',
 'No exhaustive fuzz/resource/performance or malicious preexisting-database audit.']},indent=2))

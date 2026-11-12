"""Independent exact-source boundaries and retained parser failure reproducer."""
import copy
from decimal import InvalidOperation
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root/'scripts'))
from test_full_content_snapshot import fixture,encode
from full_content_snapshot import snapshot_report,MAX_BYTES
from sidecar_digest import canonical_bytes
passed=[];failures=[]
def check(name,value):
    assert value,name
    passed.append(name)
def run(p,f,r):return snapshot_report(encode(p),encode(f),r)
def fixed(name,v):
    check(name,v['authentication']=='unverified_import' and v['recipient_decision']=='not_evaluated' and v['coverage_state']=='pending_resolver' and all(v[k]=='pending' for k in ['implementation_review','runtime_review','overall_status']) and len(v['unmet_gates'])==6 and not any(k in v for k in ['frontier_complete','full_content_available','correction_chain_complete','caller_age_bound_satisfied']))
def mutate(p,index,change):
    p=copy.deepcopy(p);v=json.loads(p['observations'][index]['result_json']);change(v['result']);p['observations'][index]['result_json']=json.dumps(v);return p
def hold(name,p,f,r):
    v=run(p,f,r);check(name+' holds',v['snapshot_state']=='hold' and v['snapshot'] is None and v['diagnostics']==['snapshot_input_or_correspondence_invalid']);fixed(name+' preserves pending gates',v)
for reply,edited in [(False,False),(False,True),(True,False),(True,True)]:
    p,f,r=fixture(reply,edited);before=encode([p,f]);v=run(p,f,r)
    check('positive '+str((reply,edited)),v['snapshot_state']=='matching_imported_full_content_observations' and v['provenance']['observations']==p['observations'] and v['inputs']['packet_raw_sha256']==hashlib.sha256(encode(p)).hexdigest() and before==encode([p,f]));fixed('positive pending '+str((reply,edited)),v)
p,f,r=fixture(True,True)
for index in [0,1,2,-2,-1]:
    for name,change in [('error',lambda v:v.update(error=None)),('partial numeric false',lambda v:v.update(partial=0)),('redacted unknown',lambda v:v.update(redacted=None))]:hold(str(index)+' '+name,mutate(p,index,change),f,r)
for name,change in [('author boolean owner',lambda v:v['author'].update(user_id=True)),('boolean count',lambda v:v.update(reply_count=False)),('unsafe count',lambda v:v.update(reply_count=2**53)),('null author',lambda v:v.update(author=None)),('missing editor',lambda v:v.pop('edited_by')),('missing status',lambda v:v.pop('status')),('unknown parent',lambda v:v.update(parent_post_id='unknown')),('summary only',lambda v:(v.pop('body'),v.update(body_summary='not full text')))]:hold(name,mutate(p,1,change),f,r)
for name,change in [('pinned boolean revision',lambda v:v.update(revision=True)),('pinned status drift',lambda v:v.update(status='done')),('pinned editor drift',lambda v:v.update(edited_by=None))]:hold(name,mutate(p,-2,change),f,r)
for index in range(len(p['observations'])):
    q=copy.deepcopy(p);q['observations'][index]['is_error']=0;hold('is_error numeric '+str(index),q,f,r)
for field,value in [('capture_id','88888888-8888-4888-8888-888888888888'),('receipt_raw_sha256','0'*64),('frontier_raw_sha256','0'*64),('reviewed_commit','e'*40),('target_commit','HEAD')]:
    q=copy.deepcopy(p);q[field]=value;hold('binding '+field,q,f,r)
for value in ['2026-02-30T00:00:00Z','2026-11-11T04:00:00+00:00','2026-11-11T04:00:00.1234567Z','2026-11-11T04:00:00']:
    q=copy.deepcopy(p);q['observations'][0]['observed_at']=value;hold('time '+value,q,f,r)
for reasons in [['opaque_transport_failure'],['replies_require_full_review','opaque_transport_failure'],['replies_require_full_review']*2]:
    q=copy.deepcopy(p);g=copy.deepcopy(f);g['diagnostics']=reasons;q['frontier_raw_sha256']=hashlib.sha256(encode(g)).hexdigest();hold('raw reason '+json.dumps(reasons),q,g,r)
for raw in [b'\xff',b'{"x":1,"x":2}',b'['*65+b']'*65,b'{"x":"\\ud800"}',b' '*(MAX_BYTES+1)]:
    v=snapshot_report(raw,encode(f),r);check('malformed outer '+str(len(raw)),v['snapshot_state']=='hold');fixed('malformed fixed '+str(len(raw)),v)
for raw in ['{"x":1,"x":2}','{"x":NaN}','{"x":"\\ud800"}','['*65+']'*65,'{}'+' '*262145]:
    q=copy.deepcopy(p);q['observations'][1]['result_json']=raw;hold('malformed inner '+str(len(raw)),q,f,r)
q=copy.deepcopy(p)
for index in [1,-2,-1]:q=mutate(q,index,lambda v:v.update(title='',body='é\r\ne\u0301'))
v=run(q,f,r);check('exact UTF8 and newline hashing',v['snapshot_state']=='matching_imported_full_content_observations' and v['snapshot']['body_sha256']==hashlib.sha256('é\r\ne\u0301'.encode()).hexdigest());fixed('invented coherent content remains unverified',v)
with patch('sqlite3.connect',side_effect=AssertionError('No SQL')),patch('socket.socket',side_effect=AssertionError('No socket')):fixed('no SQL/socket in process',run(p,f,r))

def extreme_packet(token):
    q=copy.deepcopy(p);raw=q['observations'][0]['result_json'];q['observations'][0]['result_json']=raw[:-1]+',"ignored_numeric_metadata":'+token+'}';return q
for token in ['1e999999999999999999999999','1e-999999999999999999999999']:
    q=extreme_packet(token)
    try:run(q,f,r)
    except InvalidOperation:
        failures.append({'finding':'S10-R1-F1','token':token,'position':'ignored outer wrapper metadata on retained profile response','exception':'decimal.InvalidOperation','expected':'bounded constant-diagnostic hold','actual':'uncaught exception'})
        check('F1 reproduced '+token,True)
    else:raise AssertionError('Frozen F1 unexpectedly changed')

with tempfile.TemporaryDirectory(prefix='factfinder-S10-') as tmp:
    d=Path(tmp)
    def write_inputs(q):
        for name,raw in [('packet',encode(q)),('frontier',encode(f)),('receipt',r)]:(d/name).write_bytes(raw)
    def snapshot():return {x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in d.iterdir() if x.is_file()}
    cli=[sys.executable,'-B',str(root/'scripts/full_content_snapshot.py')]
    for name in ['packet','frontier','receipt']:cli+=['--'+name,str(d/name)]
    write_inputs(p);before=snapshot();good=subprocess.run(cli,capture_output=True,timeout=30);check('actual CLI positive preserves all bytes/file set',good.returncode==0 and json.loads(good.stdout)['snapshot_state']=='matching_imported_full_content_observations' and before==snapshot())
    (d/'packet').write_bytes(b' '*(MAX_BYTES+1));before=snapshot();bad=subprocess.run(cli,capture_output=True,timeout=30);check('oversize CLI emits bounded hold without traceback',bad.returncode==0 and json.loads(bad.stdout)['snapshot_state']=='hold' and b'Traceback' not in bad.stderr and before==snapshot())
    write_inputs(extreme_packet('1e999999999999999999999999'));before=snapshot();bad=subprocess.run(cli,capture_output=True,timeout=30)
    check('F1 actual CLI nonzero traceback and no JSON report',bad.returncode==1 and bad.stdout==b'' and b'Traceback' in bad.stderr and b'decimal.InvalidOperation' in bad.stderr)
    check('F1 CLI does not mutate inputs/file set',before==snapshot())

print(json.dumps({'schema_version':1,'subject_commit':'e3295bd5b27a7b05a778e471fd8f7a4f4e501cad','fixture_kind':'inspected_existing_S6_and_S10_synthetic_fixtures_with_new_boundary_mutations','assertion_count':len(passed),'passed':passed,'reproduced_failures':failures,'live_capture_used':False,'shared_source_edited':False},indent=2))

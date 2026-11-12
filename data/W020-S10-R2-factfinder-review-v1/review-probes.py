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
# Reuse the inspected R1 boundary checks, then exercise the narrow fix at every
# retained response position and both wrapper levels with fresh numeric vectors.
tokens_bad=['1e999999999999999999999999','1e-999999999999999999999999','-1e999999999999999999999999','0.0e999999999999999999999999']
tokens_good=['0.25','1e-25','-0.0','1.7976931348623157e308','1e-10000']
for index in range(len(p['observations'])):
    for nested in [False,True]:
        for token in tokens_bad+tokens_good:
            q=copy.deepcopy(p);raw=q['observations'][index]['result_json']
            if nested:
                value=json.loads(raw);inner=json.dumps(value['result']);value['result']=None
                raw=json.dumps(value).replace('"result": null','"result": '+inner[:-1]+',"ignored_numeric_metadata":'+token+'}')
            else:raw=raw[:-1]+',"ignored_numeric_metadata":'+token+'}'
            q['observations'][index]['result_json']=raw;before=encode(q);out=run(q,f,r)
            label='numeric '+str(index)+' '+str(nested)+' '+token
            if token in tokens_bad:
                check(label,out['snapshot_state']=='hold' and out['snapshot'] is None and out['diagnostics']==['snapshot_input_or_correspondence_invalid'] and token not in json.dumps(out));fixed(label+' pending',out)
                check(label+' original prerequisite',out['prerequisite']['original_collector_diagnostics']==f['diagnostics'] and out['prerequisite']['original_observation_state']==f['observation_state'])
            else:
                check(label,out['snapshot_state']=='matching_imported_full_content_observations' and out['provenance']['observations']==q['observations'] and out['provenance']['result_json_sha256'][index]==hashlib.sha256(raw.encode()).hexdigest());fixed(label+' pending',out)
            check(label+' no mutation',encode(q)==before)
with tempfile.TemporaryDirectory(prefix='factfinder-S10-R2-') as tmp:
    d=Path(tmp)
    for token in tokens_bad+tokens_good:
        q=extreme_packet(token);files={'packet':encode(q),'frontier':encode(f),'receipt':r}
        for name,raw in files.items():(d/name).write_bytes(raw)
        cmd=[sys.executable,'-B',str(root/'scripts/full_content_snapshot.py')]
        for name in files:cmd+=['--'+name,str(d/name)]
        cli=subprocess.run(cmd,cwd=tmp,capture_output=True,timeout=30);expected=run(q,f,r)
        check('CLI '+token,cli.returncode==0 and cli.stderr==b'' and json.loads(cli.stdout)==expected and len(cli.stdout)<=MAX_BYTES+1)
        check('CLI preserves inputs '+token,{x.name:x.read_bytes() for x in d.iterdir()}==files)
result={'schema_version':1,'subject_commit':'2a72a7485b8698bdaceb06370b03563feff9d492','fixture_kind':'inspected_R1_S6_S10_synthetic_fixtures_plus_new_numeric_position_wrapper_boundary_vectors','assertion_count':len(passed),'passed':passed,'findings':[],'F1_extreme_numeric_vectors':len(tokens_bad),'ordinary_numeric_vectors':len(tokens_good),'numeric_response_positions':len(p['observations']),'wrapper_levels':2,'live_capture_used':False,'shared_source_edited':False}
print(json.dumps(result,indent=2))

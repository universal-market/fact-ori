"""Independent imported-response relationship probes; no remote or SQL operations."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root/'scripts'))
from verify_review_frontier import verify_frontier
generated=json.loads(subprocess.check_output(['node',str(Path(__file__).with_suffix('.mjs')),str(root)],timeout=30))
normal=generated['envelope'];receipt=generated['receipt'].encode()
enc=lambda v:json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()
passed=[]
def check(name,condition):
    assert condition,name
    passed.append(name)
def run(v=normal,r=receipt):return verify_frontier(enc(v),r)
def mutate(group,index,change,v=None):
    v=copy.deepcopy(normal if v is None else v)
    obs=(v['capture']['observations'] if group=='base' else v['observations'])[index]
    payload=json.loads(obs['result_json']);change(payload['result']);obs['result_json']=json.dumps(payload)
    return v
def pending(name,v):
    result=run(v)
    check(name+' remains pending',result['response_relationships']=='pending' and bool(result['diagnostics']))
    return result
def check_authority(name,result):
    check(name,result['authentication']=='unverified_import' and result['implementation_review']=='pending' and result['runtime_review']=='pending' and result['source_binding']=='unchecked')

result=run();check('synthetic actual S4 output internally matches',result['response_relationships']=='matching_imported_observations' and result['derived_frontier_complete'] and result['derived_reply_refs']==[])
check_authority('matching responses never gain authority',result)
check('raw input/receipt digest domains retained',result['frontier_raw_sha256']==hashlib.sha256(enc(normal)).hexdigest() and result['receipt_raw_sha256']==hashlib.sha256(receipt).hexdigest())
for group,index,label,change in [
 ('base',0,'wrong recorder',lambda p:p['profile'].update(id=normal['capture']['reviewer_agent_id'])),
 ('base',0,'human recorder',lambda p:p['profile'].update(kind='human')),
 ('base',0,'array recorder owner',lambda p:p['profile'].update(user_id=[p['profile']['user_id']])),
 ('base',0,'boolean recorder owner',lambda p:p['profile'].update(user_id=True)),
 ('base',1,'wrong reviewer',lambda p:p.update(id=normal['capture']['recorder_agent_id'])),
 ('base',1,'human reviewer',lambda p:p.update(kind='human')),
 ('base',1,'changed reviewer owner',lambda p:p.update(user_id=normal['capture']['recorder_agent_id'])),
 ('base',2,'first post kind',lambda p:p.update(kind='community')),
 ('base',2,'first author',lambda p:p['author'].update(id=normal['capture']['recorder_agent_id'])),
 ('base',2,'first owner',lambda p:p['author'].update(user_id=normal['capture']['recorder_agent_id'])),
 ('base',2,'missing status',lambda p:p.pop('status')),
 ('base',2,'missing editor',lambda p:p.pop('edited_by')),
 ('base',3,'pinned post',lambda p:p.update(post_id=normal['capture']['recorder_agent_id'])),
 ('base',3,'pinned text',lambda p:p.update(body='different')),
 ('base',3,'pinned editor',lambda p:p.update(edited_by={'id':normal['capture']['recorder_agent_id']})),
 ('extra',1,'last title',lambda p:p.update(title='changed')),
 ('extra',1,'last body',lambda p:p.update(body='withdrawn')),
 ('extra',1,'last revision',lambda p:p.update(revision=2)),
 ('extra',1,'last author',lambda p:p['author'].update(id=normal['capture']['recorder_agent_id'])),
 ('extra',1,'last owner',lambda p:p['author'].update(user_id=normal['capture']['recorder_agent_id'])),
 ('extra',1,'last status',lambda p:p.update(status='done')),
 ('extra',1,'last count',lambda p:p.update(reply_count=1)),
 ('extra',1,'last missing editor',lambda p:p.pop('edited_by')),
]:pending(label,mutate(group,index,change))
for group,index,field in [('base',2,'revision'),('base',3,'revision'),('extra',1,'reply_count')]:
    for value in [True,1.0,'1',[],None]:
        pending(group+str(index)+' '+field+' '+json.dumps(value),mutate(group,index,lambda p:p.update({field:value})))
for field,value in [('id',1.0),('id',True),('user_id',1.0),('user_id',True)]:
    pending('reviewer '+field+' '+json.dumps(value),mutate('base',1,lambda p:p.update({field:value})))
for raw in ['{}','{"error":null}','{"result":{"error":false}}','{"result":[]}','{"result":null}']:
    v=copy.deepcopy(normal);v['capture']['observations'][3]['result_json']=raw;pending('pinned raw '+raw,v)
def two_pages():
    v=mutate('extra',0,lambda p:p.update(next_cursor='A'))
    second=copy.deepcopy(normal['observations'][0]);second['arguments']['cursor']='A'
    v['observations'].insert(1,second);v['pages_read']=2
    return v
v=two_pages();check('empty page continuation internally matches',run(v)['response_relationships']=='matching_imported_observations')
v['observations'][1]['arguments']['cursor']='wrong';pending('cursor request differs from prior response',v)
pending('extra page after null termination',mutate('extra',0,lambda p:p.update(next_cursor=None),two_pages()))
pending('response cursor cycle',mutate('extra',1,lambda p:p.update(next_cursor='A'),two_pages()))
pending('claimed complete hides response cursor',mutate('extra',0,lambda p:p.update(next_cursor='A')))
for value in [True,1,'true']:
    pending('partial flag '+json.dumps(value),mutate('extra',0,lambda p:p.update(partial=value)))
for label,change in [('missing cursor',lambda p:p.pop('next_cursor')),('array cursor',lambda p:p.update(next_cursor=[])),('array items',lambda p:p.update(items={})),('bad reply',lambda p:p.update(items=[{'post':[]}]))]:pending(label,mutate('extra',0,change))
ref={'post_id':'66666666-6666-4666-8666-666666666666','revision':1,'author_agent_id':normal['capture']['recorder_agent_id'],'author_owner_id':normal['capture']['reviewer_owner_id']}
reply={'post':{'kind':'post','id':ref['post_id'],'revision':1,'author':{'id':ref['author_agent_id'],'user_id':ref['author_owner_id']},'body_summary':'just an acknowledgment'}}
v=mutate('extra',0,lambda p:p.update(items=[reply]))
v=mutate('base',2,lambda p:p.update(reply_count=1),v);v=mutate('extra',1,lambda p:p.update(reply_count=1),v)
pending('reply omitted from claimed refs',v)
v.update(reply_refs=[ref],diagnostics=['replies_require_full_review'],observation_state='pending')
r=pending('benign-looking third-party reply still needs disposition',v)
check('exact reply refs reconstructed',r['derived_reply_refs']==[ref] and 'replies_require_full_content_disposition' in r['diagnostics'])
pending('duplicate response reply ids',mutate('extra',0,lambda p:p.update(items=[reply,reply]),v))
pending('decimal response reply revision',mutate('extra',0,lambda p:p['items'][0]['post'].update(revision=1.0),v))
v=copy.deepcopy(normal);v.update(diagnostics=['opaque_pending_reason'],observation_state='pending');r=pending('collector diagnostics not cleared',v)
check('collector diagnostic marker retained','collector_reported_pending' in r['diagnostics'] and 'collector_state_pending' in r['diagnostics'])
v=mutate('extra',0,lambda p:p.update(next_cursor='A'));v.update(frontier_complete=False,next_cursor='A',diagnostics=['budget_exhausted'],observation_state='pending');pending('consistent incomplete frontier',v)
v=copy.deepcopy(normal);v['observations']=v['observations'][:1];v.update(diagnostics=['no_final_read'],observation_state='pending');pending('missing final reread',v)
for field,value in [('pages_read',True),('implementation_review','accepted')]:
    v=copy.deepcopy(normal);v[field]=value
    try:run(v)
    except ValueError:check('structural '+field+' rejects',True)
    else:raise AssertionError('structural rejection missing')
try:run(normal,receipt+b' ')
except ValueError:check('receipt binding failure raises',True)
else:raise AssertionError('receipt mismatch')
v=copy.deepcopy(normal)
for obs in [v['capture']['observations'][2],v['capture']['observations'][3],v['observations'][-1]]:
    p=json.loads(obs['result_json']);p['result']['body']='REVISE; synthetic fully consistent forgery';obs['result_json']=json.dumps(p)
r=run(v);check('consistent fabricated prose sequence only internally matches',r['response_relationships']=='matching_imported_observations');check_authority('fully consistent forgery still unverified',r)
with patch('sqlite3.connect',side_effect=AssertionError('SQL is forbidden in verifier')):
    check('verifier opens no SQLite connection',run()['response_relationships']=='matching_imported_observations')
with tempfile.TemporaryDirectory(prefix='factfinder-S6-') as tmp:
    tmp=Path(tmp);fp=tmp/'frontier.json';rp=tmp/'receipt.json';fp.write_bytes(enc(normal));rp.write_bytes(receipt)
    cli=[sys.executable,'-B',str(root/'scripts/verify_review_frontier.py'),'--frontier',str(fp),'--receipt',str(rp)]
    output=subprocess.run(cli,capture_output=True,timeout=30)
    check('actual CLI emits matching unverified output',output.returncode==0 and json.loads(output.stdout)['response_relationships']=='matching_imported_observations')
    check('CLI preserves files and creates no database',fp.read_bytes()==enc(normal) and rp.read_bytes()==receipt and {p.name for p in tmp.iterdir()}=={'frontier.json','receipt.json'})
    fp.write_bytes(b'{');bad=subprocess.run(cli,capture_output=True,timeout=30)
    check('malformed CLI input exit2',bad.returncode==2 and b'Frontier verification failed' in bad.stderr)
print(json.dumps({'schema_version':1,'subject_commit':'f448fad3ac9793a3f49fb0b37082749a315e74cd','fixture_kind':'synthetic_actual_S4_output_and_read_only_verifier','assertion_count':len(passed),'passed':passed,'findings':[]},indent=2))

"""Additional exact-source probes; public pinned fixtures, no active integration."""
import copy,hashlib,json,sqlite3,socket,sys
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root/'scripts'))
from c007a_preview import evaluate,InvalidPreview
raw=[(root/p).read_bytes() for p in ['data/C007a-v3-routing-proposal-v1-2026-11-12.json','scripts/fixtures/c007a-v3/record.json','scripts/fixtures/c007a-v3/source-review.json']]
p,r,s=map(json.loads,raw)
author='a5bef1e6-09b1-4f0a-8fce-17d830ee8660';fm='e94a196f-fcdb-4a14-b6e6-e02d50abe5d3';owner='167fdd40-59f0-49d1-a287-ac76a0998090'
ids={'5575d2c1-8870-4a59-9d5d-eeb932cbf745':author,'b4558d95-1af8-4301-a8f1-ca3efa297358':fm,'fc08478f-7043-4c7d-aae5-a9654556dd91':fm}
ctx={k:dict(revision=1,status=None,author_agent_id=v,owner_id=owner,correction_state='clear') for k,v in ids.items()}
passed=[]
def ck(name,x):
 assert x,name
 passed.append(name)
def run(q=None,rr=None,posts=None):return evaluate(q if q is not None else p['fixtures'][0]['query'],*(rr if rr is not None else raw),current_posts=ctx if posts is None else posts)
def gates(name,v):ck(name,v['answer'] is None and v['api_activation'] is False and v['curation']=='pending' and v['query_routing_implementation_review']=='pending' and v['input_authentication']=='unverified_caller_supplied_context' and v['remaining_gate_requirements']==p['gates_before_any_answer'][1:])
def reject(name,fn):
 try:fn()
 except InvalidPreview as e:ck(name,str(e)=='c007a_preview_input_invalid')
 else:raise AssertionError(name)
expected=[('eligible_after_gates','P1'),('eligible_after_gates','P2'),('eligible_after_gates','P3'),('clarify_metric',None),('clarify_date_surface',None)]+[('outside_scope',None)]*10
for f,exp in zip(p['fixtures'],expected):
 v=run(f['query']);ck(f['id']+' exact authored scope',(v['proposed_after_gates'],v['predicate'])==exp and v['required_constraint']==f['required_constraint']);gates(f['id']+' fixed gates',v)
 for suffix in [' ','\n',' today',' exactly to 0.01m']:
  v=run(f['query']+suffix);ck(f['id']+' altered '+repr(suffix),v['fixture_id'] is None and v['predicate'] is None and v['required_constraint'] is None and v['proposed_after_gates']=='unmapped');gates(f['id']+' altered fixed '+repr(suffix),v)
for id in ids:
 for field in ['revision','status','author_agent_id','owner_id','correction_state']:
  for value in [True,False,0,1.0,'1',[],{},'unknown','unresolved','withdrawn']:
   if field=='status' and value is None:continue
   c=copy.deepcopy(ctx);c[id][field]=value;reject(id+' '+field+' '+repr(value),lambda c=c:run(posts=c))
  c=copy.deepcopy(ctx);del c[id][field];reject(id+' missing '+field,lambda c=c:run(posts=c))
 for field in ['api_activation','curation','review_accepted']:
  c=copy.deepcopy(ctx);c[id][field]=True;reject(id+' injected '+field,lambda c=c:run(posts=c))
 c=copy.deepcopy(ctx);c[id]=None;reject(id+' null row',lambda c=c:run(posts=c))
for i in range(3):
 for change in [b'',b'{}',b'\xff',b'NaN',raw[i]+b' ',bytearray(raw[i]),raw[(i+1)%3]]:
  rr=list(raw);rr[i]=change;reject('raw domain '+str(i)+' '+str(type(change))+' '+str(len(change)),lambda rr=rr:run(rr=rr))
for q in [True,False,0,{},[],b'query','', '\t\n','x'*2001]:reject('query '+repr(q)[:60],lambda q=q:evaluate(q,*raw,current_posts=ctx))
for q in ['x'*2000,'unseen query','Which summit is highest above global mean sea level?\u200b']:
 v=run(q);ck('unmapped bounded query '+str(len(q)),v['proposed_after_gates']=='unmapped');gates('unmapped gates '+str(len(q)),v)
v=run();ck('complete substantive limitations retained',v['limitations']==r['limitations'][1:]);ck('creation history exact',v['creation_time_history']==p['proposed_projection']['creation_time_history']);ck('full source coverage retained',v['source_review_coverage']==s['coverage']);ck('source dependence retained',v['source_dependence']==s['source_dependence']);ck('roles and predicate map retained',v['roles']==p['roles'] and v['predicate_sources']==p['predicate_sources']);ck('both exact bindings retained',v['candidate_binding']==p['candidate_binding'] and v['source_review_binding']==p['source_review_binding'])
before=copy.deepcopy(ctx);hashes=[hashlib.sha256(x).hexdigest() for x in raw]
v['candidate_binding'].clear();v['roles'].clear();v['limitations'].clear();v['creation_time_history'].clear();v['source_review_coverage'].clear();v['remaining_gate_requirements'].clear()
w=run();ck('deepcopy protects repeated outputs',w['candidate_binding']==p['candidate_binding'] and w['limitations']==r['limitations'][1:] and w['source_review_coverage']==s['coverage']);ck('caller input context unchanged',ctx==before);ck('raw input bytes unchanged',[hashlib.sha256(x).hexdigest() for x in raw]==hashes)
with patch('sqlite3.connect',side_effect=AssertionError('SQL')),patch('socket.socket',side_effect=AssertionError('network')):gates('in-process no SQL/socket',run())
print(json.dumps({'schema_version':1,'subject_commit':'18df8b2ea6a20fa97e8b6d0e1611d1cb95238a6c','assertion_count':len(passed),'passed':passed,'findings':[],'fixture_kind':'reviewed_public_frozen_design_and_candidate_source_review_copies_with_additional_mutations','coherent_invented_context_used':True,'live_capture_used':False,'shared_source_edited':False},indent=2))

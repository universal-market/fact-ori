"""Exact-source detached attachment review probes, never active curation."""
import copy,hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root/'scripts'))
from c007a_pending import derive_pending_view,InvalidAttachment
from ask import lookup
from library_view import load_view
from export_api_seed import build_snapshot
from export_public_snapshot import export_public
fix=root/'scripts/fixtures/c007a-v3'
raw=[(root/'data/C007a-v3-routing-proposal-v1-2026-11-12.json').read_bytes(),(fix/'record.json').read_bytes(),(fix/'source-review.json').read_bytes()]
p,r,s=map(json.loads,raw);manifest=json.loads((fix/'attachment-manifest-v1.json').read_bytes())
ids={'5575d2c1-8870-4a59-9d5d-eeb932cbf745':'a5bef1e6-09b1-4f0a-8fce-17d830ee8660','b4558d95-1af8-4301-a8f1-ca3efa297358':'e94a196f-fcdb-4a14-b6e6-e02d50abe5d3','fc08478f-7043-4c7d-aae5-a9654556dd91':'e94a196f-fcdb-4a14-b6e6-e02d50abe5d3'}
ctx={k:dict(revision=1,status=None,author_agent_id=v,owner_id='167fdd40-59f0-49d1-a287-ac76a0998090',correction_state='clear') for k,v in ids.items()}
passed=[]
def ck(n,x):
 assert x,n
 passed.append(n)
def run(attachments=None,state='pending',posts=None,rr=None):return derive_pending_view(*(raw if rr is None else rr),[manifest] if attachments is None else attachments,current_posts=ctx if posts is None else posts,selection_state=state)
def reject(n,fn):
 try:fn()
 except InvalidAttachment as e:ck(n,str(e)=='c007a_pending_attachment_invalid')
 else:raise AssertionError(n)
def withheld(n,v):
 c=v['claims'][0];ck(n,c['answer'] is None and c['answer_kind']=='withheld' and c['api_activation'] is False and c['curation_state']=='not_evaluated' and c['query_routing_implementation_review']=='pending' and c['curation_event'] is None and c['selection_is_curation_receipt'] is False and c['reviews']==[] and v['input_authentication']=='unverified_caller_supplied_context')
active_paths=['data/library-inputs.json','data/curation-events.json','data/query-catalog.json','public/library.json'];before_files={x:(root/x).read_bytes() for x in active_paths};baseline=(load_view(root),build_snapshot(root),export_public(root))
catalog={'schema_version':1,'routing_review_status':'reviewed','routes':[{'kind':'claim','claim_id':'C007a','version':3,'record_sha256':manifest['candidate_binding']['record_digest'],'questions':[f['query'] for f in p['fixtures'][:3]]}]}
for state in ['pending','reopened','retired','unselected']:
 v=run(state=state);c=v['claims'][0];withheld(state+' gates',v);ck(state+' display only',v['offline_selection_only'] is True and c['state']==state and c['selected_version']==(None if state=='unselected' else 3))
 for f in p['fixtures'][:3]:
  q=lookup(f['query'],v,catalog);ck(state+' '+f['id']+' existing lookup withholds',q['status']=='withheld' and q['answer'] is None)
for state in ['approved','accept','pending ',True,False,1,1.0,None,[],{},'']:
 reject('invalid selection '+repr(state),lambda state=state:run(state=state))
for a in [[],{},[None],[manifest,manifest],[manifest,{}],[{'decision':'accept'}],True]:reject('invalid attachment container '+repr(a)[:60],lambda a=a:run(attachments=a))
def paths(v,prefix=()):
 if type(v) is dict:
  for k,x in v.items():yield from paths(x,prefix+(k,))
 else:yield prefix,v
for path,old in paths(manifest):
 for value in [None,True,1.0,'changed']:
  if type(old)==type(value) and old==value:continue
  m=copy.deepcopy(manifest);ref=m
  for k in path[:-1]:ref=ref[k]
  ref[path[-1]]=value;reject('manifest '+'.'.join(path)+' '+repr(value),lambda m=m:run([m]))
 m=copy.deepcopy(manifest);ref=m
 for k in path[:-1]:ref=ref[k]
 del ref[path[-1]];reject('manifest missing '+'.'.join(path),lambda m=m:run([m]))
for group in [None,'candidate_binding','source_review_binding']:
 m=copy.deepcopy(manifest);(m if group is None else m[group])['api_activation']=True;reject('manifest injected gate '+str(group),lambda m=m:run([m]))
for id in ctx:
 for field in ctx[id]:
  for value in [True,False,1.0,{},[],None,'unknown','unresolved','withdrawn']:
   if type(ctx[id][field])==type(value) and ctx[id][field]==value:continue
   c=copy.deepcopy(ctx);c[id][field]=value;reject('context '+id+' '+field+' '+repr(value),lambda c=c:run(posts=c))
  c=copy.deepcopy(ctx);del c[id][field];reject('context missing '+id+' '+field,lambda c=c:run(posts=c))
 c=copy.deepcopy(ctx);c[id]['curation']='approved';reject('context extra gate '+id,lambda c=c:run(posts=c))
for i in range(3):
 for value in [b'',b'{}',b'\xff',raw[i]+b' ',bytearray(raw[i]),raw[(i+1)%3]]:
  rr=list(raw);rr[i]=value;reject('raw '+str(i)+' '+str(type(value))+' '+str(len(value)),lambda rr=rr:run(rr=rr))
v=run();c=v['claims'][0];a=c['detached_source_reviews'][0]
ck('entire original review retained',a['original_artifact']==s);ck('exact attachment retained',a['attachment_manifest']==manifest);ck('review raw hash domain',a['raw_sha256']==hashlib.sha256(raw[2]).hexdigest());ck('review canonical hash domain',a['canonical_sha256']==hashlib.sha256(json.dumps(s,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
ck('history targets remain separate',c['history'][0]['review_decisions']==[] and c['history'][0]['detached_source_review_decisions']==[s['decision']]);ck('all substantive limitations retained',c['limitations']==r['limitations'][1:]);ck('exact creation history retained',c['historical_draft_metadata']==p['proposed_projection']['creation_time_history']);ck('coverage dependence roles retained',c['source_review_coverage']==s['coverage'] and c['source_dependence']==s['source_dependence'] and c['roles']==p['roles']);ck('pending snapshot byte reproduction',json.dumps(v,indent=2,ensure_ascii=False)+'\n'==(fix/'pending-view-v1.json').read_text())
before=copy.deepcopy((ctx,manifest,raw));c['detached_source_reviews'][0]['original_artifact'].clear();c['detached_source_reviews'][0]['attachment_manifest'].clear();c['limitations'].clear();c['history'].clear();c['historical_draft_metadata'].clear();ck('caller inputs isolated',(ctx,manifest,raw)==before);ck('future result isolated',run()['claims'][0]['detached_source_reviews'][0]['original_artifact']==s)
with patch('sqlite3.connect',side_effect=AssertionError('SQL')),patch('socket.socket',side_effect=AssertionError('network')):withheld('no SQL/socket',run())
ck('existing view seed public export unchanged',baseline==(load_view(root),build_snapshot(root),export_public(root)));ck('eight existing records exclude C007a',len(baseline[0]['claims'])==8 and all(x['claim_id']!='C007a' for x in baseline[0]['claims']));ck('all active input bytes unchanged',before_files=={x:(root/x).read_bytes() for x in active_paths})
print(json.dumps({'schema_version':1,'subject_commit':'68cf2bce2f979fe542cadec2df1c560cc5d46fbb','assertion_count':len(passed),'passed':passed,'findings':[],'fixture_kind':'inspected_public_frozen_design_record_review_manifest_and_invented_context_with_new_nested_mutations','live_capture_used':False,'shared_source_edited':False},indent=2))

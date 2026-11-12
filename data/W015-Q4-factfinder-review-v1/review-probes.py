"""Exact offline literal-routing and proposed-text/source review probes."""
import copy,hashlib,json,sys,unicodedata
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root/'scripts'))
from c007a_routes import route_pending,InvalidRoute
from library_view import load_view,InvalidLibrary
from ask import lookup
from export_api_seed import build_snapshot
from export_public_snapshot import export_public
fix=root/'scripts/fixtures/c007a-v3';catraw=(fix/'predicate-catalog-v1.json').read_bytes();cat=json.loads(catraw)
raw=[(root/'data/C007a-v3-routing-proposal-v1-2026-11-12.json').read_bytes(),(fix/'record.json').read_bytes(),(fix/'source-review.json').read_bytes()];proposal,record,review=map(json.loads,raw);att=[json.loads((fix/'attachment-manifest-v1.json').read_bytes())]
ids={'5575d2c1-8870-4a59-9d5d-eeb932cbf745':'a5bef1e6-09b1-4f0a-8fce-17d830ee8660','b4558d95-1af8-4301-a8f1-ca3efa297358':'e94a196f-fcdb-4a14-b6e6-e02d50abe5d3','fc08478f-7043-4c7d-aae5-a9654556dd91':'e94a196f-fcdb-4a14-b6e6-e02d50abe5d3'};ctx={k:dict(revision=1,status=None,author_agent_id=v,owner_id='167fdd40-59f0-49d1-a287-ac76a0998090',correction_state='clear') for k,v in ids.items()}
passed=[]
def ck(n,x):
 assert x,n
 passed.append(n)
def run(q=None,catalog=None,rr=None,attachments=None,posts=None,state='pending'):return route_pending(cat['routes'][0]['query'] if q is None else q,catraw if catalog is None else catalog,*(raw if rr is None else rr),att if attachments is None else attachments,current_posts=ctx if posts is None else posts,selection_state=state)
def reject(n,fn):
 try:fn()
 except InvalidRoute as e:ck(n,str(e)=='c007a_literal_route_invalid')
 else:raise AssertionError(n)
def gates(n,v):
 c=v['pending_audit_view']['claims'][0];ck(n,v['status']=='withheld' and v['answer'] is None and v['answer_kind']=='withheld' and v['api_activation'] is False and v['curation_state']=='not_evaluated' and v['curation_event'] is None and v['routing_review_status']=='unreviewed' and v['input_authentication']=='unverified_caller_supplied_context' and v['audit_proposal']['approval']=='unreviewed_not_for_answering' and v['audit_proposal']['unmapped_is_factual_false'] is False and c['answer'] is None and c['api_activation'] is False)
expected=[('P1',['S1'],'Mount Everest is the highest point above global mean sea level.'),('P2',['S3a'],'Nepal and China jointly announced a snow-surface height of 8,848.86 m for Mount Everest on 2020-12-08.'),('P3',['S2'],'The participating Nepal technical report describes an orthometric height referenced to the International Height Reference System (IHRS).')]
active_paths=['data/library-inputs.json','data/curation-events.json','data/query-catalog.json','public/library.json'];before_files={x:(root/x).read_bytes() for x in active_paths};baseline=(load_view(root),build_snapshot(root),export_public(root));inputs=copy.deepcopy((att,ctx,raw,catraw))
for state in ['pending','reopened','retired','unselected']:
 for i,row in enumerate(cat['routes']):
  v=run(row['query'],state=state);gates(state+' '+row['fixture_id']+' gates',v);a=v['audit_proposal'];ck(state+' '+row['fixture_id']+' constraint',a['route']['required_constraint']==proposal['fixtures'][i]['required_constraint'])
  if i<3:
   pred,src,text=expected[i];ck(state+' '+row['fixture_id']+' text/source isolation',a['route']['predicate']==pred and a['route']['source_ids']==src and a['route']['proposed_answer']==text and a['selected_sources']==[x for x in record['evidence'] if x['source_id'] in src] and text!=record['answer'])
  else:ck(state+' '+row['fixture_id']+' no text/source',a['route']['proposed_answer'] is None and a['selected_sources']==[] and a['route']['predicate'] is None and a['route']['proposed_disposition']==('clarify_metric' if i==3 else 'clarify_date_surface' if i==4 else 'outside_scope'))
for row in cat['routes']:
 q=row['query']
 for changed in [q.upper(),q.lower(),q+' ',q+'\n',q+'\u200b',q+'\u2060',' '+q,q.replace(' ','\u00a0'),q.replace(' ','  '),q[:-1],q+' today']:
  if changed==q:continue
  v=run(changed);ck(row['fixture_id']+' literal '+repr(changed),v['audit_proposal']['route'] is None and v['audit_proposal']['selected_sources']==[]);gates(row['fixture_id']+' literal gates '+repr(changed),v)
for i,row in enumerate(cat['routes']):
 for field,value in [('predicate','P3'),('source_ids',['S2']),('proposed_answer','unapproved compound'),('query',cat['routes'][0]['query']),('fixture_id',True)]:
  c=copy.deepcopy(cat);c['routes'][i][field]=value;reject('catalog row '+str(i)+' '+field,lambda c=c:run(catalog=json.dumps(c).encode()))
for field,value in [('schema_version',True),('catalog_version',1.0),('review_status','reviewed'),('api_activation',True),('matching','casefold')]:
 c=copy.deepcopy(cat);c[field]=value;reject('catalog '+field,lambda c=c:run(catalog=json.dumps(c).encode()))
c=copy.deepcopy(cat);c['routes'].append(c['routes'][0]);reject('duplicate query catalog',lambda:run(catalog=json.dumps(c).encode()))
for value in [b'',b'{}',b'\xff',catraw+b' ',bytearray(catraw)]:reject('catalog raw '+str(type(value))+' '+str(len(value)),lambda value=value:run(catalog=value))
for id in ctx:
 for field,value in [('revision',True),('revision',1.0),('status','done'),('author_agent_id','changed'),('owner_id','changed'),('correction_state','unknown'),('correction_state','unresolved'),('correction_state','withdrawn')]:
  c=copy.deepcopy(ctx);c[id][field]=value;reject('context '+id+' '+field+' '+str(value),lambda c=c:run(posts=c))
for state in ['approved','accepted',True,None,[],{},'pending ']:reject('selection '+repr(state),lambda state=state:run(state=state))
for attachments in [[],att*2,[{}],[None]]:reject('attachment '+repr(attachments)[:45],lambda attachments=attachments:run(attachments=attachments))
for i in range(3):
 rr=list(raw);rr[i]+=b' ';reject('raw input '+str(i),lambda rr=rr:run(rr=rr))
for q in [True,1,[],{},'', '\n','x'*2001]:reject('query '+repr(q)[:30],lambda q=q:route_pending(q,catraw,*raw,att,current_posts=ctx))
rows=[run(r['query']) for r in cat['routes']];ck('all15row snapshot exact',json.dumps(rows,indent=2,ensure_ascii=False)+'\n'==(fix/'predicate-route-results-v1.json').read_text())
try:lookup(cat['routes'][0]['query'],load_view(root),cat)
except InvalidLibrary:ck('legacy schema1 fails closed on schema2',True)
else:raise AssertionError('legacy downgrade')
v=run();c=v['pending_audit_view']['claims'][0];ck('complete original review retained',c['detached_source_reviews'][0]['original_artifact']==review);ck('all substantive limits retained',c['limitations']==record['limitations'][1:]);ck('full coverage dependence history retained',c['source_review_coverage']==review['coverage'] and c['source_dependence']==review['source_dependence'] and c['historical_draft_metadata']==proposal['proposed_projection']['creation_time_history'])
v['audit_proposal']['selected_sources'][0].clear();v['audit_proposal']['route'].clear();v['candidate_binding'].clear();c['detached_source_reviews'].clear();ck('caller inputs unchanged',inputs==(att,ctx,raw,catraw));ck('future output isolated',run()['audit_proposal']['route']['proposed_answer']==expected[0][2])
with patch('sqlite3.connect',side_effect=AssertionError('SQL')),patch('socket.socket',side_effect=AssertionError('network')):gates('no SQL/socket',run())
ck('existing view seed public export unchanged',baseline==(load_view(root),build_snapshot(root),export_public(root)));ck('eightrecords exclude C007a',len(baseline[0]['claims'])==8 and all(c['claim_id']!='C007a' for c in baseline[0]['claims']));ck('four active bytes unchanged',before_files=={x:(root/x).read_bytes() for x in active_paths})
print(json.dumps({'schema_version':1,'subject_commit':'153d3385171049f3c3faaf3e66cd1f8ca0fe3f63','assertion_count':len(passed),'passed':passed,'findings':[],'fixture_kind':'inspected_frozen_design_catalog_record_review_with_independent_exact_text_oracle_and_new_mutations','live_capture_used':False,'shared_source_edited':False},indent=2))

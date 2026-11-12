"""Factfinder finite offline Q5 boundary probes. Run with exact source root argument."""
import copy, hashlib, json, sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(); sys.path.insert(0,str(root/'scripts'))
from ask import lookup_pending, lookup
from export_api_seed import build_pending_snapshot, build_snapshot
from export_public_snapshot import export_pending, export_public
from library_view import load_view, InvalidLibrary
from c007a_consumer import InvalidPendingConsumer
from c007a_preview import OWNER, POSTS
fix=root/'scripts/fixtures/c007a-v3'
inputs=[(fix/'predicate-catalog-v1.json').read_bytes(),(root/'data/C007a-v3-routing-proposal-v1-2026-11-12.json').read_bytes(),(fix/'record.json').read_bytes(),(fix/'source-review.json').read_bytes(),[json.loads((fix/'attachment-manifest-v1.json').read_text())]]
posts={k:dict(revision=1,status=None,author_agent_id=a,owner_id=OWNER,correction_state='clear') for k,a in POSTS.items()}
rows=json.loads(inputs[0])['routes']; results=[]
def check(label,condition):
    assert condition,label
    results.append(label)
def rejected(label,fn):
    try: fn()
    except InvalidPendingConsumer as e: check(label,str(e)=='c007a_pending_consumer_invalid')
    else: raise AssertionError(label)
def consumers(seed,ins=inputs,ctx=None,state='pending'):
    context=dict(current_posts=posts if ctx is None else ctx,selection_state=state)
    return [lambda:lookup_pending(rows[0]['query'],seed,*ins,**context),lambda:export_pending(seed,*ins,**context)]
ctx=dict(current_posts=posts,selection_state='pending')
seed=json.loads(json.dumps(build_pending_snapshot(*inputs,**ctx)))
original=copy.deepcopy((inputs,posts,seed))
for state in ['pending','reopened','retired','unselected']:
    s=json.loads(json.dumps(build_pending_snapshot(*inputs,current_posts=posts,selection_state=state)))
    for i,row in enumerate(rows):
        r=lookup_pending(row['query'],s,*inputs,current_posts=posts,selection_state=state)
        check(f'{state}/route/{i}',r['status']=='withheld' and r['answer'] is None and r['api_activation'] is False and r['curation_event'] is None and all(r['route_diagnostic'][k]==row[k] for k in ['predicate','source_ids','required_constraint']))
    e=export_pending(s,*inputs,current_posts=posts,selection_state=state)
    check(f'{state}/export',e['records']==[] and e['exact_mappings']==[] and e['withheld'][0]['state']==state and e['not_for_publication'] is True)
    if state!='pending':
        for n,f in enumerate(consumers(seed,state=state)): rejected(f'stale-state/{state}/{n}',f)
for i,row in enumerate(rows):
    for j,q in enumerate([row['query']+' ',row['query']+'\u200b',row['query'].upper(),row['query'][:-1]]):
        r=lookup_pending(q,seed,*inputs,**ctx)
        check(f'changedliteral/{i}/{j}',r['status']=='not_in_library' and r['route_diagnostic'] is None and r['answer'] is None and r['missing_coverage_is_factual_false'] is False)
# Mutate every serialized leaf individually; do not merely test top-level fields.
def leaves(v,p=()):
    if isinstance(v,dict):
        for k,x in v.items(): yield from leaves(x,p+(k,))
    elif isinstance(v,list):
        for k,x in enumerate(v): yield from leaves(x,p+(k,))
    else: yield p,v
for i,(path,value) in enumerate(leaves(seed)):
    changed=copy.deepcopy(seed); parent=changed
    for key in path[:-1]: parent=parent[key]
    parent[path[-1]]=('tampered' if value!='tampered' else None)
    for n,f in enumerate(consumers(changed)): rejected(f'leaf/{i}/{n}',f)
changes=[]
for key,value in [('schema_version',True),('format_version',1.0),('answer','injected'),('extra',{}),('digest','f'*64)]:
    s=copy.deepcopy(seed);s[key]=value;changes.append(s)
for key in ['audit_refs','withheld_claim']:
    s=copy.deepcopy(seed);s[key]['extra']=False;changes.append(s)
s=copy.deepcopy(seed);s['literal_routes'].append(copy.deepcopy(s['literal_routes'][0]));changes.append(s)
s=copy.deepcopy(seed);s['literal_routes'][0]['proposed_answer']='injected';changes.append(s)
for i,s in enumerate(changes):
    for n,f in enumerate(consumers(s)): rejected(f'structure/{i}/{n}',f)
for id in posts:
    for field,value in [('revision',2),('revision',True),('status','withdrawn'),('correction_state','unknown'),('author_agent_id','wrong'),('owner_id','wrong')]:
        p=copy.deepcopy(posts);p[id][field]=value
        for n,f in enumerate(consumers(seed,ctx=p)): rejected(f'context/{id}/{field}/{value}/{n}',f)
p=copy.deepcopy(posts);p.pop(next(iter(p)))
for n,f in enumerate(consumers(seed,ctx=p)): rejected(f'context/missing/{n}',f)
for i in range(4):
    ins=copy.deepcopy(inputs);ins[i]+=b' '
    for n,f in enumerate(consumers(seed,ins=ins)): rejected(f'raw/{i}/{n}',f)
for i,a in enumerate([[],inputs[4]*2,[{}]]):
    ins=copy.deepcopy(inputs);ins[4]=a
    for n,f in enumerate(consumers(seed,ins=ins)):rejected(f'attachment/{i}/{n}',f)
for i,q in enumerate([True,None,'',' '*2,'x'*2001]):rejected(f'question/{i}',lambda:lookup_pending(q,seed,*inputs,**ctx))
outputs=[seed,export_pending(seed,*inputs,**ctx)]+[lookup_pending(r['query'],seed,*inputs,**ctx) for r in rows]
forbidden={'proposed_answer','original_artifact','pending_audit_view','canonicalRecord','claim_under_review','selected_sources'}
def clean(v):
    if isinstance(v,dict):return not forbidden.intersection(v) and all(clean(x) for x in v.values())
    if isinstance(v,list):return all(clean(x) for x in v)
    return True
for i,o in enumerate(outputs):
    check(f'body-omission/{i}',clean(o) and all(r['proposed_answer'] not in json.dumps(o) for r in rows[:3]))
    check(f'audit-hashes/{i}',all(o['audit_refs'][key]==hashlib.sha256(inputs[j]).hexdigest() for key,j in [('catalog_raw_sha256',0),('proposal_raw_sha256',1),('record_raw_sha256',2),('review_raw_sha256',3)]))
q=lookup_pending(rows[0]['query'],seed,*inputs,**ctx);q['audit_refs'].clear();q['route_diagnostic'].clear()
e=export_pending(seed,*inputs,**ctx);e['withheld'].clear();e['audit_refs'].clear()
check('mutation-isolation',(inputs,posts,seed)==original)
check('schema-separation',not any(k in seed for k in ['versions','claims','aliases','importId']))
try:lookup(rows[0]['query'],load_view(root),seed)
except InvalidLibrary:check('legacy-rejects',True)
else:raise AssertionError('legacy accepted schema2')
snapshot=build_snapshot(root); public=export_public(root)
check('default-import-id',snapshot['importId']=='e78b021826f2b202abcc257cf1f49116cb376d004cb70ee2613a0b8e90499d53')
check('default-count',len(load_view(root)['claims'])==8)
# Match public CLI serialization used by implementation.
encoded=(json.dumps(public,indent=2,ensure_ascii=False)+'\n').encode()
check('default-public-sha256',public['snapshot_sha256']=='1cf35fb47563862540b0a343cc02f65633665826c509fcea3eeb4f641bda2b23')
fixture={'seed':seed,'queries':outputs[2:],'export':outputs[1]}
check('exact-frozen-fixture',(json.dumps(fixture,indent=2,ensure_ascii=False)+'\n').encode()==(fix/'pending-consumer-results-v1.json').read_bytes())
print(json.dumps(dict(schema_version=1,task='FO-W015-Q5',passed=len(results),failed=0,checks=results,context='Invented unverified fixture context; no remote authenticity or factual truth established.'),indent=2)+'\n',end='')

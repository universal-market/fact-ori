"""Detached design binding/fixture audit; never a production routing test."""
import hashlib,json,subprocess
from pathlib import Path
passed=[]
def check(name,ok):
    assert ok,name
    passed.append(name)
def raw(commit,path):return subprocess.check_output(['git','show',commit+':'+path])
def sha(b):return hashlib.sha256(b).hexdigest()
praw=raw('cdfa2208e82e2e288b2784adbf7309366995d2e8','data/C007a-v3-routing-proposal-v1-2026-11-12.json');p=json.loads(praw)
check('exact proposal raw hash',sha(praw)=='f169442090e89785d4f58c3107bf73087c1fbc72cbb0089d3a4ff181e530b112')
c=p['candidate_binding'];rraw=raw(c['commit'],c['directory']+'/record.json');r=json.loads(rraw)
s=p['source_review_binding'];sraw=raw(s['commit'],s['path']);review=json.loads(sraw)
check('record raw binding',sha(rraw)==c['record_raw_sha256']);check('record canonical digest',sha(json.dumps(r,sort_keys=True,separators=(',',':')).encode())==c['record_digest'])
for name,h in c['file_hashes'].items():check('candidate file '+name,sha(raw(c['commit'],c['directory']+'/'+name))==h)
check('candidate manifest raw binding',sha(raw(c['commit'],c['directory']+'/file-hashes.json'))==c['manifest_raw_sha256'])
check('review raw binding',sha(sraw)==s['raw_sha256']);check('complete review input binding',review['input']==c)
check('source decision distinct from curation',review['decision']['review_decision']=='accept' and review['decision']['curation']=='pending' and review['decision']['query_routing']=='pending' and review['decision']['api_activation'] is False)
check('creation-time history remains original',r['review_status']=='awaiting_review' and r['reviews']==[] and p['proposed_projection']['creation_time_history']['review_notes']==[r['limitations'][0]])
check('source verdict exact projection',p['proposed_projection']['current_exact_source_review']['decision']==review['decision']['review_decision'] and p['proposed_projection']['current_exact_source_review']['evidence_verdict']==review['decision']['evidence_verdict'] and p['proposed_projection']['current_exact_source_review']['scope']==review['decision']['scope'])
check('all original candidate decisions remain pending',r['decisions']=={'exact_candidate_review':'pending','curation':'pending','query_routing':'not_reviewed','api_activation':False})
check('proposal never activates',p['proposed_projection']['answer'] is None and p['proposed_projection']['api_activation'] is False and p['proposed_projection']['curation']=='pending' and p['proposed_projection']['query_routing_review']=='pending')
check('predicate source map unchanged',p['predicate_sources']=={x['predicate_id']:x['source_ids'] for x in r['predicate_source_map']})
expected=[('eligible_after_gates','P1'),('eligible_after_gates','P2'),('eligible_after_gates','P3'),('clarify_metric',None),('clarify_date_surface',None)]+[('outside_scope',None)]*10
check('fifteen unique ordered fixture IDs',[x['id'] for x in p['fixtures']]==['Q%02d'%i for i in range(1,16)])
for x,(route,predicate) in zip(p['fixtures'],expected):check(x['id']+' inspected authored disposition',x['current_answer'] is None and (x['proposed_after_gates'],x['predicate'])==(route,predicate) and bool(x['required_constraint']))
check('nine distinct prospective negative criteria',len(p['binding_negative_criteria'])==9 and len(set(p['binding_negative_criteria']))==9)
check('five separate prospective answer gates',len(p['gates_before_any_answer'])==5)
print(json.dumps({'schema_version':1,'kind':'detached_exact_design_audit','checks':len(passed),'passed':passed,'production_router_executed':False,'negative_attachment_mutations_executed':False,'source_factual_recheck':False,'interpretation':'Bindings/structure/manual-disposition oracle only. Nine negative attachment criteria are reviewed prose, not exercised implementation rejection.'},indent=2))

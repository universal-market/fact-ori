"""Offline reviewer checks of exact C013 artifacts; no routing implementation."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

SCOPE='0044769cc907727b31ddc5613dc538ee2fafe27c'
ADAPTER='87994ebd4dd103e0b9f416b105a932807cbfeec5'
def raw(path,commit):return subprocess.check_output(['git','show',commit+':'+path])
def read(path):return json.loads(Path(path).read_bytes())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
m=read('data/C013-routing-proposal-input-v2.json')
bindings=[]
for entry in [dict(path='data/C013-routing-proposal-input-v2.json',commit=SCOPE,raw_sha256='b7d8cb516f5a8dd6b3997ed496388f7a9b8be34ccec14543f60650a56ad2b342'),m['proposal'],*m['frozen_inputs']]:
    commit=SCOPE if entry['commit']=='this_scope_commit' else entry['commit']
    data=raw(entry['path'],commit)
    assert hashlib.sha256(data).hexdigest()==entry['raw_sha256']
    assert data==Path(entry['path']).read_bytes()
    bindings.append(dict(path=entry['path'],commit=commit,raw_sha256=entry['raw_sha256'],git_workspace_equal=True))
p=read('data/C013-routing-proposal-v2.json');old=read('data/C013-routing-proposal-v1.json')
fixtures={r['id']:r for r in p['fixtures']}
assert len(fixtures)==22 and all(fixtures[r['id']]==r for r in old['fixtures']) and len(old['fixtures'])==20
assert all(r['current_answer'] is None for r in fixtures.values())
assert all(not r['proposed_after_all_gates_response'].startswith(('Yes','No')) for i,r in fixtures.items() if i.startswith('N') or i=='P03')
assert all(r['proposed_after_all_gates_response'] is None for i,r in fixtures.items() if i[0] in 'XAMTS')
b=read('data/C013-exact-review-attached-bundle-v1.json');record=read('data/C013-library-candidate-v1/record.json')
review=read('data/C013-v1-factfinder-exact-review-v1.json');a=b['reviews'][0]
events=read('data/C013-reviewed-pending-events-v1.json');revisions=read('data/C013-library-candidate-v1/post-revisions.json')
published=read('data/C013-reviewed-pending-view-v1.json')
assert b['records']==[record] and len(b['reviews'])==1
assert digest(record)==a['input_record_sha256']==review['input']['record_digest']==p['candidate']['record_digest']
assert a['receipt']['raw_sha256']==hashlib.sha256(Path('data/C013-v1-factfinder-exact-review-v1.json').read_bytes()).hexdigest()
assert a['receipt']['canonical_sha256']==digest(review)
assert a['reviewed_post_revision']==review['input']['reviewed_post_revision']==p['candidate']['post_revision']==1
assert a['reviewed_post_id']==review['input']['reviewed_post_id']==p['candidate']['post_id']
assert a['review_decision']==review['decision']['review_decision']=='accept'
assert a['coverage']==review['coverage'] and a['routing_followup']==review['routing_followup']
assert a['relationship_disclosure']==review['roles']['disclosure']
assert events[0]==read('data/C013-library-candidate-v1/pending-events.json')[0]
assert all(e['state']=='pending' for e in events)

# Load only pinned historical pure projection/validator, without main/load_view.
aux=[]
for name in ('validate_pilot','library_view'):
    path='scripts/'+name+'.py';data=raw(path,ADAPTER)
    aux.append(dict(path=path,commit=ADAPTER,raw_sha256=hashlib.sha256(data).hexdigest()))
    mod=types.ModuleType(name);mod.__file__=path;sys.modules[name]=mod
    exec(compile(data,path,'exec'),mod.__dict__)
project=sys.modules['library_view'].derive_view
actual=project([b],events,revisions)
assert actual==published
claim=actual['claims'][0]
assert claim['state']=='pending' and claim['answer'] is None and claim['answer_kind']=='withheld'
assert claim['source_dependence_groups']==['noaa-educational-account']
assert claim['limitations'][:2]==record['limitations'][:2]
stale=record['limitations'][2]
assert stale in claim['limitations'] and stale not in claim['historical_draft_metadata']['review_notes']
assert claim['current_review_state']=='accepted' and len(claim['reviews'])==1

negative=[]
for name in ('record_digest','anchor_revision','duplicate_review','wrong_claim_version'):
    bb,ee,rr=copy.deepcopy((b,events,revisions))
    if name=='record_digest':ee[-1]['record_sha256']='0'*64
    if name=='anchor_revision':ee[-1]['post_revision']=2
    if name=='duplicate_review':bb['reviews'].append(copy.deepcopy(bb['reviews'][0]))
    if name=='wrong_claim_version':bb['reviews'][0]['claim_version']=2
    try:project([bb],ee,rr)
    except ValueError as error:negative.append(dict(case=name,rejected=True,error=str(error)))
    else:raise AssertionError('expected rejection '+name)

# Disclosed boundary: this consistency projector does not authenticate remote receipts.
changed=copy.deepcopy(b);changed['reviews'][0]['receipt']['raw_sha256']='0'*64
receipt_mutation_projection=project([changed],events,revisions)
assert receipt_mutation_projection==actual
print(json.dumps(dict(schema_version=1,scope='offline exact artifacts; no router or source research',bindings=bindings,auxiliary_projection_code=aux,checks=dict(exact_pins=18,original_fixtures_preserved=20,authored_fixture_total=22,all_current_answers_withheld=True,frozen_record_exact=True,source_review_raw_and_canonical_bindings=True,coverage_roles_routing_limits_preserved=True,projection_matches_published=True,original_event_prefix_preserved=True,one_noaa_group_preserved=True),negative_controls=negative,observed_defect=dict(id='A1',path='data/C013-reviewed-pending-view-v1.json',pointer='/claims/0/limitations/2',value=stale,current_review_state=claim['current_review_state'],attached_review_count=len(claim['reviews']),historical_review_notes=claim['historical_draft_metadata']['review_notes']),unchecked_enforcement=dict(receipt_hash_mutation_ignored_by_consistency_projector=True,meaning='Current exact external receipt bytes verified separately above; no runtime receipt-authentication or general binding-rejection implementation acceptance.')),indent=2))

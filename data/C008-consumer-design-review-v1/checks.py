"""Exact offline design checks; does not implement the proposed consumer map."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

SCOPE='f187ddaa2cae1deda2772b941aff205a077f9164'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
m=read('data/C008-consumer-design-input-v1.json');bindings=[]
for b in [dict(path='data/C008-consumer-design-input-v1.json',commit=SCOPE,raw_sha256='d52d8f7ba42786e9dd546b5cb19e70bf3110154bc3bfe5071aed4aec1dbeb65b'),m['proposal'],*m['frozen_inputs']]:
    c=SCOPE if b['commit']=='this_scope_commit' else b['commit']
    raw=subprocess.check_output(['git','show',c+':'+b['path']])
    assert hashlib.sha256(raw).hexdigest()==b['raw_sha256'] and raw==Path(b['path']).read_bytes()
    bindings.append(dict(path=b['path'],commit=c,raw_sha256=b['raw_sha256'],git_workspace_equal=True))
p=read('data/C008-consumer-design-v1.json');record=read('data/C008-factfinder-candidate-v1/record.json')
review=read('data/C008-v1-factomaton-source-review-v1.json');bundle=read('data/C008-factfinder-candidate-v1/bundle.json')
assert bundle['records']==[record] and bundle['reviews']==[]
assert record['claim']=='The Great Wall of China is visible from the Moon with the naked eye.'
assert record['verdict']==p['candidate']['factual_verdict']==review['decision']['evidence_verdict']=='contradicted'
assert record['answer']==p['candidate']['answer']=="No. NASA states that the Great Wall isn't visible from the Moon."
assert digest(record)==p['candidate']['record_digest']==review['input']['record_digest']
assert review['input']['record_raw_sha256']==p['candidate']['record_raw_sha256']
assert record['tilori_post_id']==p['candidate']['anchor_post_id']==review['input']['reviewed_post_id']
assert record['tilori_post_revision']==p['candidate']['anchor_revision']==review['input']['reviewed_post_revision']==1
assert p['proposed_answer_kind_map']=={'supported':'supported_assertion','insufficient_evidence':'reviewed_abstention','contradicted':'reviewed_contradiction'}
cases=p['fixtures'];assert len(cases)==len({r['id'] for r in cases})==18
assert all(r['current_answer'] is None for r in cases)
assert all(r['proposed_response_after_all_gates'] is None for r in cases if not r['id'].startswith('M'))
assert all(not r['proposed_response_after_all_gates'].startswith(('Yes','No')) for r in cases if r['id'] in ('M02','M03','M04','M05'))
assert len({s['dependence_group'] for s in record['evidence']})==1
assert record['evidence'][1]['relation']=='context_only'
assert p['exact_source_review']['raw_sha256']==hashlib.sha256(Path(p['exact_source_review']['path']).read_bytes()).hexdigest()
assert review['decision']['review_decision']=='accept' and review['decision']['api_activation'] is False
assert review['decision']['curation']==review['decision']['query_routing']=='pending'

# Inspect existing approved snapshot boundary without invoking any routing code.
snapshot=read('public/library.json');c009=next(r for r in snapshot['records'] if r['claim_id']=='C009')
assert c009['version']==2 and c009['sha256']==p['C009_boundary']['record_digest']==digest(c009['record'])
assert c009['record']['verdict']=='insufficient_evidence'
assert not any(r['claim_id']=='C008' for r in snapshot['records'])
catalog=read('data/query-catalog.json');routes=[r for r in catalog['routes'] if r.get('claim_id')=='C009']
assert len(routes)==1 and routes[0]['version']==2
assert all(r.get('claim_id')!='C008' for r in catalog['routes'])

# Execute only pinned existing pure validator/projection. No guard removal or new map.
for name in ('validate_pilot','library_view'):
    path='scripts/'+name+'.py';raw=Path(path).read_bytes();mod=types.ModuleType(name);mod.__file__=path;sys.modules[name]=mod
    exec(compile(raw,path,'exec'),mod.__dict__)
assert sys.modules['validate_pilot'].validate(bundle)==[]
try:
    sys.modules['library_view'].derive_view([bundle],read('data/C008-factfinder-candidate-v1/pending-events.json'),read('data/C008-factfinder-candidate-v1/post-revisions.json'))
except ValueError as error:
    rejection=str(error);assert 'unsupported verdict' in rejection
else:raise AssertionError('existing projection unexpectedly accepts C008')
print(json.dumps(dict(schema_version=1,scope='offline exact design and boundary checks only',bindings=bindings,checks=dict(scope_pin_count=len(bindings),frozen_candidate_and_review_bound=True,positive_claim_contradicted_verdict_attributed_negative_answer_preserved=True,three_explicit_distinct_design_kinds=True,unique_authored_cases=18,current_C008_answers_all_null=True,negative_interrogative_tag_and_nested_cases_no_leading_yes_no=True,single_nasa_family_and_distance_context_only=True,C009_v2_digest_and_insufficient_evidence_preserved=True,existing_C009_route_questions_unchanged=routes[0]['questions'],C008_absent_from_active_records_and_routes=True,existing_bundle_schema_errors=[],existing_projection_error=rejection),limits=['Proposed map is data inspected for semantic completeness, not executed consumer implementation.','Unknown-verdict rejection, migration/exports/schema compatibility and gate enforcement remain future implementation obligations.','No NASA refetch, optical experiment, router/alias/model/backend/deployment or factual revalidation.']),indent=2))

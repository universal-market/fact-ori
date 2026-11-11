"""Detached v2 policy vectors with unchanged S6; no S10 adapter implementation."""
import copy
import hashlib
import itertools
import json
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root/'scripts'))
from test_verify_review_frontier import SemanticFrontierTests
from verify_review_frontier import verify_frontier
enc=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode()
sha=lambda b:hashlib.sha256(b).hexdigest()
f=SemanticFrontierTests();f.setUp();baseline=copy.deepcopy(f.value);receipt=f.receipt
expected_markers=['replies_require_full_content_disposition','collector_reported_pending','collector_state_pending']
def policy(value,result):
    # Literal interpretation of the reviewed table; a design oracle only.
    if result['frontier_raw_sha256']!=sha(enc(value)) or result['receipt_raw_sha256']!=sha(receipt):return False
    if not result['derived_frontier_complete'] or result['derived_next_cursor'] is not None:return False
    refs=result['derived_reply_refs'];reasons=value.get('diagnostics');state=value.get('observation_state')
    return ((not refs and reasons==[] and state=='empty_frontier_observed' and result['diagnostics']==[]) or
            (bool(refs) and reasons==['replies_require_full_review'] and state=='pending' and result['diagnostics']==expected_markers))
def frontier(with_reply):
    value=copy.deepcopy(baseline)
    if with_reply:
        cap=value['capture'];ref={'post_id':'66666666-6666-4666-8666-666666666666','revision':1,'author_agent_id':cap['recorder_agent_id'],'author_owner_id':cap['reviewer_owner_id']}
        child={'kind':'post','id':ref['post_id'],'revision':1,'parent_post_id':cap['decision_post_id'],'author':{'id':ref['author_agent_id'],'user_id':ref['author_owner_id']}}
        for o in [cap['observations'][2],value['observations'][-1]]:
            p=json.loads(o['result_json']);p['result']['reply_count']=1;o['result_json']=json.dumps(p)
        value['observations'][0]['result_json']=json.dumps({'result':{'items':[{'post':child}],'next_cursor':None}})
        value['reply_refs']=[ref]
    return value
reason_cases=[('empty',[]),('expected',['replies_require_full_review']),('unknown',['opaque_transport_failure']),('mixed',['replies_require_full_review','opaque_transport_failure']),('duplicate',['replies_require_full_review']*2),('future',['replies_require_full_review_v2']),('missing',None),('nonarray',{})]
states=['empty_frontier_observed','pending','future_state',None]
rows=[]
for has_reply,(label,reasons),state in itertools.product([False,True],reason_cases,states):
    v=frontier(has_reply);v['observation_state']=state
    if label=='missing':v.pop('diagnostics')
    else:v['diagnostics']=reasons
    expected=((not has_reply and label=='empty' and state=='empty_frontier_observed') or (has_reply and label=='expected' and state=='pending'))
    before=enc(v)
    try:r=verify_frontier(before,receipt);actual=policy(v,r);s6='returned'
    except (ValueError,TypeError,RecursionError):actual=False;s6='structural_hold'
    assert actual==expected,(has_reply,label,state)
    assert before==enc(v)
    rows.append({'reply_count':int(has_reply),'reason_case':label,'state':state,'S6':s6,'discovery_qualifies':actual,'pass':True})
assert len(rows)==64 and sum(x['discovery_qualifies'] for x in rows)==2

v=frontier(True);v.update(diagnostics=['replies_require_full_review'],observation_state='pending');r=verify_frontier(enc(v),receipt)
tamper=[]
for field,value in [('frontier_raw_sha256','0'*64),('receipt_raw_sha256','0'*64),('derived_frontier_complete',False),('derived_next_cursor','more'),('diagnostics',expected_markers+['future_diag']),('diagnostics',list(reversed(expected_markers)))]:
    changed=copy.deepcopy(r);changed[field]=value;assert not policy(v,changed);tamper.append(field)

cap=v['capture'];ref=r['derived_reply_refs'][0]
def selection(selector,initial,last):
    if initial!=last:return False
    if initial['post_id']!=selector['post_id'] or initial['revision']!=selector['revision'] or initial['parent_post_id']!=selector['parent_post_id']:return False
    if selector['post_id']==cap['decision_post_id']:
        return selector['revision']==cap['decision_revision'] and initial['author_agent_id']==cap['reviewer_agent_id'] and initial['author_owner_id']==cap['reviewer_owner_id']
    return initial['parent_post_id']==cap['decision_post_id'] and any(all(initial[k]==x[k] for k in ['post_id','revision','author_agent_id','author_owner_id']) for x in r['derived_reply_refs'])
reply={**ref,'parent_post_id':cap['decision_post_id']};selector={k:reply[k] for k in ['post_id','revision','parent_post_id']}
selection_rows=[]
def selected(name,s,a,b,expected):
    actual=selection(s,a,b);assert actual==expected,name;selection_rows.append({'id':name,'selected':actual,'pass':True})
selected('direct reply',selector,reply,reply,True)
nested={**reply,'parent_post_id':'77777777-7777-4777-8777-777777777777'};selected('nested all-depth ref cannot pass by membership',{**selector,'parent_post_id':nested['parent_post_id']},nested,nested,False)
selected('current parent drift',selector,reply,nested,False)
selected('reply owner mismatch',selector,{**reply,'author_owner_id':cap['recorder_agent_id']},{**reply,'author_owner_id':cap['recorder_agent_id']},False)
selected('unlisted revision',{**selector,'revision':2},{**reply,'revision':2},{**reply,'revision':2},False)
parent={'post_id':cap['decision_post_id'],'revision':cap['decision_revision'],'author_agent_id':cap['reviewer_agent_id'],'author_owner_id':cap['reviewer_owner_id'],'parent_post_id':'88888888-8888-4888-8888-888888888888'};ps={k:parent[k] for k in ['post_id','revision','parent_post_id']}
selected('decision keeps its own nonnull parent',ps,parent,parent,True)
selected('decision author mismatch',ps,{**parent,'author_agent_id':cap['recorder_agent_id']},{**parent,'author_agent_id':cap['recorder_agent_id']},False)
selected('decision owner mismatch',ps,{**parent,'author_owner_id':cap['recorder_agent_id']},{**parent,'author_owner_id':cap['recorder_agent_id']},False)
selected('decision selector parent mismatch',{**ps,'parent_post_id':None},parent,parent,False)

design=root/'docs/full-content-observation-adapter-design-v2.md';assert sha(design.read_bytes())=='6475dd7b04eef08acf05752249b7435fcaab07ef1bdded8b943da77ab356c560'
matrix=json.loads((root/'data/W020-S10-D2-factomaton-design-v2/case-matrix.json').read_text());assert len(matrix['cases'])==35 and len({x['id'] for x in matrix['cases']})==35 and matrix['assertions_run']==0
example=json.loads((root/'data/W020-S10-D2-factomaton-design-v2/example.synthetic.json').read_text());initial=json.loads(example['packet']['observations'][1]['result_json']);assert sha(initial['body'].encode())==example['expected_snapshot']['body_sha256'];assert sha(initial['title'].encode())==example['expected_snapshot']['title_sha256']
print(json.dumps({'schema_version':1,'kind':'detached_design_policy_vector_results','design_commit':'c26f65b3e3f1c85b8b8f8119a3f4ab7f7178197c','raw_reason_state_vectors':rows,'qualified_pairs':2,'binding_summary_tamper_vectors':len(tamper),'selector_vectors':selection_rows,'static_design_example_matrix_checks':4,'total_checked_vectors_and_static_checks':len(rows)+len(tamper)+len(selection_rows)+4,'method':'Actual unchanged S6 feeds a literal detached interpretation of the proposed v2 table; selector checks are design-rule vectors, not an implemented adapter/full-protocol test.','S10_adapter_tests_run':0,'author_criteria_executed':False,'full_regressions_rerun':False,'live_capture_used':False},indent=2))

"""Design-review evidence: exercise unchanged S6, never an S10 implementation."""
import copy
import hashlib
import json
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root/'scripts'))
from test_verify_review_frontier import SemanticFrontierTests
from verify_review_frontier import verify_frontier

passed=[]
def check(name,value):
    assert value,name
    passed.append(name)
enc=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode()
allowed={'replies_require_full_content_disposition','collector_reported_pending','collector_state_pending'}
f=SemanticFrontierTests();f.setUp();normal=copy.deepcopy(f.value);receipt=f.receipt
def report(value):return verify_frontier(enc(value),receipt)
def qualifies(r):return r['derived_frontier_complete'] and r['derived_next_cursor'] is None and set(r['diagnostics'])<=allowed
r=report(normal);check('baseline actual S6 complete',qualifies(r) and r['diagnostics']==[])
cap=normal['capture'];ref={'post_id':'66666666-6666-4666-8666-666666666666','revision':1,'author_agent_id':cap['recorder_agent_id'],'author_owner_id':cap['reviewer_owner_id']}
child={'kind':'post','id':ref['post_id'],'revision':1,'parent_post_id':cap['decision_post_id'],'author':{'id':ref['author_agent_id'],'user_id':ref['author_owner_id']}}
for o in [cap['observations'][2],normal['observations'][-1]]:
    p=json.loads(o['result_json']);p['result']['reply_count']=1;o['result_json']=json.dumps(p)
normal['observations'][0]['result_json']=json.dumps({'result':{'items':[{'post':child}],'next_cursor':None}})
normal['reply_refs']=[ref]
expected=copy.deepcopy(normal);expected.update(diagnostics=['replies_require_full_review'],observation_state='pending')
unknown=copy.deepcopy(normal);unknown.update(diagnostics=['opaque_transport_failure'],observation_state='pending')
er=report(expected);ur=report(unknown)
check('expected collector condition maps to allowed markers',qualifies(er))
check('unknown collector failure maps to same allowed markers',qualifies(ur))
check('marker allowlist cannot distinguish underlying reasons',er['diagnostics']==ur['diagnostics']==['replies_require_full_content_disposition','collector_reported_pending','collector_state_pending'] and len(er['derived_reply_refs'])==len(ur['derived_reply_refs'])==1)
check('original raw frontier hash distinguishes packets',er['frontier_raw_sha256']!=ur['frontier_raw_sha256'])
check('synthetic raw reasons remain separately available',unknown['diagnostics']==['opaque_transport_failure'] and expected['diagnostics']==['replies_require_full_review'])
check('S6 does not authenticate or approve either packet',all(r['authentication']=='unverified_import' and r['implementation_review']=='pending' and r['runtime_review']=='pending' for r in [er,ur]))

# S6 searches all descendants; its public reference projection carries no parent.
v=copy.deepcopy(normal);cap=v['capture'];nested_parent='77777777-7777-4777-8777-777777777777'
ref={'post_id':'66666666-6666-4666-8666-666666666666','revision':1,'author_agent_id':cap['recorder_agent_id'],'author_owner_id':cap['reviewer_owner_id']}
child={'kind':'post','id':ref['post_id'],'revision':1,'parent_post_id':nested_parent,'author':{'id':ref['author_agent_id'],'user_id':ref['author_owner_id']}}
for o in [cap['observations'][2],v['observations'][-1]]:
    p=json.loads(o['result_json']);p['result']['reply_count']=1;o['result_json']=json.dumps(p)
v['observations'][0]['result_json']=json.dumps({'result':{'items':[{'post':child}],'next_cursor':None}})
v.update(reply_refs=[ref],diagnostics=['replies_require_full_review'],observation_state='pending')
nr=report(v)
check('S6 derives nested reference without parent field',qualifies(nr) and nr['derived_reply_refs']==[ref] and 'parent_post_id' not in nr['derived_reply_refs'][0])
check('nested full parent differs from decision parent',child['parent_post_id']!=cap['decision_post_id'])

design=root/'docs/full-content-observation-adapter-design-v1.md'
text=design.read_text();check('reviewed design has exact frozen bytes',hashlib.sha256(design.read_bytes()).hexdigest()=='6686a84fa1d02f74195efb6d54b3866dd08837c3ae6e54bf860d27b30d68e74e')
check('design names generic marker allowlist',all(x in text for x in allowed))
example=json.loads((root/'data/W020-S10-D1-factomaton-design-v1/example.synthetic.json').read_text());p=example['packet'];initial=json.loads(p['observations'][1]['result_json'])
check('synthetic body hash arithmetic matches',hashlib.sha256(initial['body'].encode('utf8')).hexdigest()==example['expected_snapshot']['body_sha256'])
check('synthetic title hash arithmetic matches',hashlib.sha256(initial['title'].encode('utf8')).hexdigest()==example['expected_snapshot']['title_sha256'])
matrix=json.loads((root/'data/W020-S10-D1-factomaton-design-v1/case-matrix.json').read_text())
check('27 named criteria remain unexecuted',len(matrix['cases'])==27 and matrix['assertions_run']==0 and len({x['id'] for x in matrix['cases']})==27)
print(json.dumps({'schema_version':1,'kind':'design_review_antecedent_evidence','design_commit':'90a1d86ec38cc4502892f55c8ef5f23524464541','assertion_count':len(passed),'passed':passed,'comparison':{'expected_raw_collector_diagnostics':expected['diagnostics'],'unknown_raw_collector_diagnostics':unknown['diagnostics'],'expected_S6_diagnostics':er['diagnostics'],'unknown_S6_diagnostics':ur['diagnostics'],'both_qualify_under_written_S6_marker_allowlist':qualifies(er) and qualifies(ur)},'nested_selection':{'derived_ref_keys':sorted(nr['derived_reply_refs'][0]),'parent_must_be_bound_from_full_reads':True},'S10_adapter_implemented_or_run':False,'live_capture_used':False,'full_regressions_rerun':False},indent=2))

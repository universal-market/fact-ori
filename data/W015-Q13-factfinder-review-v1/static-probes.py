"""Source-only design analysis; no worker, verifier, model or fault execution."""
import pathlib,json,hashlib,subprocess,sys
root=pathlib.Path('local/W015-Q13/exact-source').resolve();d=root/'data/W015-Q13-partial-report-design-v2';read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest();m=read(d/'review-input.json');assert sha((d/'review-input.json').read_bytes())=='2b28e7097dc5e2ebb1bd7a85537caf8d886c546d3fc4abf6e412708bb0b68d00'
assert len(m['raw_bindings'])==69
for f,h in m['raw_bindings'].items():assert sha((root/f).read_bytes())==h,f
old=read(root/'data/W015-Q12-partial-report-design-v1/review-input.json')['raw_bindings'];assert len(old)==60 and all(m['raw_bindings'][f]==h for f,h in old.items())
a=read(d/'design.json');matrix=read(d/'fault-matrix.json');assert sha((d/'design.json').read_bytes())=='bc665dea4816a97045ca5c1ef1baae4bf7c9ea0e6473bba21160875b9b313603'
# Recompute expected states/reasons from explicit abstract fixture declarations.
checks=[]
for base in matrix['cases']:
 for item in [base]+base['required_variants']:
  cond=base['conditions'];states=[];reasons=[]
  whole=(not cond['worker_leader_reaped'] or cond['reconciliation_allocation_seconds']<20 or cond['reconciliation_status']!='success' or not cond['reconciliation_leader_reaped'] or not cond['reconciliation_within_deadline'] or cond['reconciliation_output']!='exact_valid')
  for i,content in enumerate(item['checkpoint_contents_by_ordinal']):
   if whole:state,reason='not_reconciled','reconciliation_unavailable'
   elif content=='absent':state,reason='unavailable','checkpoint_missing'
   elif i==1 and states[0]!='validated':state,reason='rejected','checkpoint_order_invalid'
   elif content in ['valid','valid_with_ignored_extension']:state,reason='validated','validated_match'
   else:state,reason='rejected','checkpoint_invalid'
   states.append(state);reasons.append(reason)
  assert states==item['case_states'],item['id'];assert reasons==item['reason_codes'],item['id'];assert item['projection_presence']==[s=='validated' for s in states]
  assert item['presence_by_ordinal']==['absent' if c=='absent' else 'present' for c in item['checkpoint_contents_by_ordinal']]
  checks.append({'id':item['id'],'case_states':states,'reason_codes':reasons,'static_mapping_match':True})
assert len(checks)==58 and len({x['id'] for x in checks})==58
oldids={r['id'] for r in read(root/'data/W015-Q12-partial-report-design-v1/fault-matrix.json')['cases']};assert len(oldids)==23 and oldids<={r['id'] for r in matrix['cases']}
s=a['reconciliation_schedule'];assert sum(s['phases_seconds'].values())+s['exit_seconds']+s['cleanup_seconds']+s['slack_seconds']==s['maximum_total_seconds']==s['minimum_launch_allocation_seconds']==20
assert sum(a['budget_partition_seconds'].values())==600 and sum(a['worker_phases_seconds'].values())+1+2==543<=570
boundary=[]
for remaining in [0,10,29,29.999,30,30.001,600]:
 b=min(20,remaining-10);boundary.append({'remaining_seconds':str(remaining),'B':str(b),'launch_per_design':b>=20})
assert [x['launch_per_design'] for x in boundary]==[False,False,False,False,True,True,True]
assert a['file_limits']['reconciliation_output_bytes']==16384 and a['file_limits']['reconciliation_parent_read_bytes']==16385
assert len(a['reconciliation_output_schema']['exact_root_keys'])==4 and len(a['public_case_keys'])==5 and len(a['projection_keys'])==9
# Static serialization arithmetic using frozen expected projections, not actual validation.
p=read(root/'data/W015-Q8-real-model-protocol-v1/protocol.json');fixture=read(root/'data/W015-Q11-worker-v2/fixture-results.json');projections=[]
for test in p['cases']:
 e=test['expected'];projections.append({'status':e['status'],'answer':e['answer'],'verdict':e['verdict'],'inspection':e.get('inspection'),'evidence_package_canonical_sha256':e.get('evidence_package_canonical_sha256'),'import_id':fixture['import_id'],'public_review':False,'live_source_refresh':False,'projection_source':'frozen_protocol_after_validated_match'})
encode=lambda v:json.dumps(v,separators=(',',':'),ensure_ascii=True).encode();sizes=[len(encode(v)) for v in projections];assert max(sizes)<=4096
schema_example={'schema_version':2,'run_id':'0'*32,'input_manifest_raw_sha256':'0'*64,'cases':[{'case_id':t['id'],'state':'validated','reason_code':'validated_match','checkpoint_digest':{'kind':'full','sha256':'0'*64,'observed_bytes':262144},'validated_projection':v} for t,v in zip(p['cases'],projections)]};assert len(encode(schema_example))<16384
before=(d/'static-checks.json').read_bytes();r=subprocess.run([sys.executable,'-B',str(d/'static-probes.py')],capture_output=True,text=True,timeout=10);assert r.returncode==0,(r.stdout,r.stderr);assert (d/'static-checks.json').read_bytes()==before
result={'schema_version':1,'task_key':'FO-W015-Q13','kind':'source_only_design_correction_review','bindings_verified':69,'prior_bindings_unchanged':60,'original_scenarios_preserved':23,'base_scenarios':32,'variants':26,'static_mapping_checks':checks,'budget':{'outer':600,'worker_phase_exit_cleanup_maxima':543,'verifier_phase_exit_cleanup_slack_total':20,'launch_boundary_examples':boundary},'schema':{'root_keys':4,'case_keys':5,'projection_keys':9,'projection_serialized_bytes':sizes,'example_output_serialized_bytes':len(encode(schema_example)),'output_cap':16384,'read_cap':16385,'note':'Frozen expected-data serialization example only, not verifier or runtime schema proof.'},'authored_static_probe':{'returncode':r.returncode,'stdout':r.stdout,'receipt_byte_equal':True},'runtime_faults_executed':False,'limits':'Abstract matrix mapping/arithmetic and fixed expected-data serialization only. No implemented worker/verifier/parser/file/privacy/cleanup/deadline behavior or real-model/resource feasibility established.'}
pathlib.Path('data/W015-Q13-factfinder-review-v1/static-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'bindings':69,'prior_unchanged':60,'static_scenario_mappings':58,'example_output_bytes':len(encode(schema_example)),'runtime_faults_executed':False}))

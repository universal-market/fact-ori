"""Static proposed-design consistency only. Executes no worker/verifier/fault harness."""
import hashlib,json,pathlib
root=pathlib.Path(__file__).resolve().parents[2]
d=root/'data/W015-Q13-partial-report-design-v2'
read=lambda p:json.loads(p.read_text())
a=read(d/'design.json');m=read(d/'fault-matrix.json');old=read(root/'data/W015-Q12-partial-report-design-v1/review-input.json')
for f,h in old['raw_bindings'].items():assert hashlib.sha256((root/f).read_bytes()).hexdigest()==h,f
rows=m['cases'];assert len(rows)==32 and len({r['id'] for r in rows})==32
oldids={r['id'] for r in read(root/'data/W015-Q12-partial-report-design-v1/fault-matrix.json')['cases']};assert oldids<={r['id'] for r in rows} and len(oldids)==23
count=0
for r in rows:
 assert len(r['checkpoint_contents_by_ordinal'])==len(r['presence_by_ordinal'])==len(r['case_states'])==len(r['reason_codes'])==len(r['projection_presence'])==2
 assert r['conditions'].keys()>={'worker_leader_reaped','worker_within_deadline','reconciliation_allocation_seconds','reconciliation_status','reconciliation_leader_reaped','reconciliation_within_deadline','reconciliation_output','directory_cleanup_success','report_path','events'}
 for v in [r]+r['required_variants']:
  for i in range(2):
   assert v['presence_by_ordinal'][i]==('absent' if v['checkpoint_contents_by_ordinal'][i]=='absent' else 'present')
   assert v['case_states'][i] in a['case_states'] and v['reason_codes'][i] in a['case_reason_codes']
   assert v['projection_presence'][i]==(v['case_states'][i]=='validated')
  if v['case_states'][0]=='rejected':
   assert v['case_states'][1]==('unavailable' if v['presence_by_ordinal'][1]=='absent' else 'rejected')
   assert v['reason_codes'][1]==('checkpoint_missing' if v['presence_by_ordinal'][1]=='absent' else 'checkpoint_order_invalid')
 count+=len(r['required_variants'])
 if r['worker_status']!='success':assert not r['expected'].startswith('passed')
assert count==26
s=a['reconciliation_schedule'];assert sum(s['phases_seconds'].values())+s['exit_seconds']+s['cleanup_seconds']+s['slack_seconds']==s['maximum_total_seconds']==20
assert s['minimum_launch_allocation_seconds']==20
assert sum(a['budget_partition_seconds'].values())==600
assert sum(a['worker_phases_seconds'].values())+1+2==543<=570
assert a['file_limits']['reconciliation_output_bytes']+1==a['file_limits']['reconciliation_parent_read_bytes']==16385
assert len(a['reconciliation_output_schema']['exact_root_keys'])==4 and len(a['public_case_keys'])==5 and len(a['projection_keys'])==9
assert len(a['failure_code_vocabulary'])==10 and len(set(a['failure_code_vocabulary']))==10
assert not set(a['projection_keys'])&{'reason','candidates','model_assessment','run_id','path','result','prompt','exception'}
result={'schema_version':1,'task_key':'FO-W015-Q13','kind':'design_static_consistency_only','status':'pass_static_only','prior_bindings_unchanged':60,'original_scenarios_preserved':23,'base_scenarios':32,'required_explicit_variants':26,'worker_phase_exit_cleanup_maxima_seconds':543,'reconciliation_phase_exit_cleanup_slack_seconds':20,'outer_partition_seconds':600,'reconciliation_output_cap_plus_one':16385,'runtime_faults_executed':False,'limits':'Checks authored design structure/arithmetic, not implementation, scenario execution, parser/race/privacy/cleanup/deadline feasibility or factual/curation/routing/API approval.'}
(d/'static-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

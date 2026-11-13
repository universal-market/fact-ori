"""Source-only Q12 design analysis, not a worker/reconciler or runtime fault test."""
import pathlib,json,hashlib,itertools
root=pathlib.Path('local/W015-Q12/exact-source');d=root/'data/W015-Q12-partial-report-design-v1';sha=lambda b:hashlib.sha256(b).hexdigest();manifest=d/'review-input.json';m=json.loads(manifest.read_text());assert sha(manifest.read_bytes())=='c9fd19378b2b8fd13fc84e2766d30d82b90d2d0cff0c0b5c121074379b92a9dc'
assert len(m['raw_bindings'])==60
for f,h in m['raw_bindings'].items():assert sha((root/f).read_bytes())==h,f
old=json.loads((root/'data/W015-Q11-worker-v2/review-input.json').read_text())['raw_bindings'];assert len(old)==51 and all(m['raw_bindings'][f]==h for f,h in old.items())
a=json.loads((d/'design.json').read_text());matrix=json.loads((d/'fault-matrix.json').read_text());doc=(root/'docs/diagnostic-partial-report-design-v1.md').read_text();p=json.loads((root/'data/W015-Q8-real-model-protocol-v1/protocol.json').read_text());assert sha((d/'design.json').read_bytes())=='c5e3e9dc7b138007ad8f493f3bc0303e37bccb21dff8640ffdcf5246c06a64fe'
rows=matrix['cases'];assert len(rows)==23 and len({x['id'] for x in rows})==23
assert a['basis']['case_ids']==[x['id'] for x in p['cases']]
assert sum(a['budget_partition_seconds'].values())==a['overall_budget_seconds']==600
assert sum(a['worker_phases_seconds'].values())+2==542<=570
for x in rows:
 assert len(x['case_states'])==2 and set(x['case_states'])<=set(a['case_states'])
 if x['worker_status']!='success':assert not x['expected'].startswith('passed')
 assert not x['expected'].startswith('passed') or x['case_states']==['validated','validated']
assert set(a['projection_keys'])=={'status','answer','verdict','inspection','evidence_package_canonical_sha256','import_id','public_review','live_source_refresh','projection_source'}
assert not set(a['projection_keys'])&{'reason','candidates','model_assessment','run_id','path','result','prompt','exception'}
assert 'No checkpoint means unavailable' in doc and 'checkpoint two is never published' in doc
ambiguous=['wrong_run_binding','wrong_input_or_pin','duplicate_keys_or_non_utf8','oversized_or_symlink_file'];byid={x['id']:x for x in rows}
for k in ambiguous:assert byid[k]['case_states']==['rejected','unavailable'] and byid[k]['worker_status']=='success'
assert byid['invalid_first_valid_second']['case_states']==['rejected','rejected']
assert byid['event_without_file']['worker_status']=='success' and byid['event_without_file']['case_states']==['unavailable','unavailable']
# Abstract presence/state alternatives, not executable implementation semantics.
alternatives=[{'first':'present_invalid','second_file':presence,'permitted_state_interpretation':['rejected','unavailable' if presence=='absent' else 'rejected_or_explicit_withheld_state']} for presence in ['absent','present']]
# All eight success prerequisites must hold. Enumerate abstract Boolean gate combinations only.
gates=['worker_success_and_phases','worker_reaped','worker_within_deadline','both_checkpoint_prefix_valid','verifier_success_reaped_within_cap','report_within_limit','owned_cleanup_success','fresh_report_write_success'];combos=list(itertools.product([False,True],repeat=len(gates)));assert sum(all(c) for c in combos)==1
capkeys=[k for k,v in a['file_limits'].items() if 'reconcil' in k or 'verif' in k];assert not capkeys
result={'schema_version':1,'task_key':'FO-W015-Q12','kind':'source_only_design_static_review','runtime_faults_executed':False,'manifest_raw_sha256':sha(manifest.read_bytes()),'bindings_verified':60,'prior_bindings_unchanged':51,'budget_arithmetic':{'partition_sum':600,'worker_phases_plus_default_cleanup':542,'worker_cap':570,'verifier_total_cap':20,'final_reserve':10},'scenario_rows_checked':23,'matrix_observations':{'ambiguous_rows':[byid[k] for k in ambiguous],'explicit_present_second_reference':byid['invalid_first_valid_second'],'metadata_not_presence_counterexample':byid['event_without_file'],'abstract_presence_alternatives':alternatives},'numeric_caps_observation':{'reconciliation_output_file_bytes':None,'explicit_verifier_phase_seconds':None,'note':'Prose requires bounded file and phase fitting remaining budget, but design provides no numeric file cap or verifier phase/cleanup values.'},'abstract_success_gate_analysis':{'gates':gates,'combinations':len(combos),'passing_combinations':1,'note':'Reviewer truth-table reasoning only; no executable reconciler, supervisor or fault run.'},'projection_key_check':'Frozen finite fields only; raw extensions excluded by design, not runtime tested.','limits':['No design edits, implementation or child/model/Docker/network execution.','Static checks support design reasoning, not parser/filesystem/privacy/resource/lifecycle feasibility proof.']}
pathlib.Path('data/W015-Q12-factfinder-review-v1/static-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'bindings':60,'prior_unchanged':51,'matrix_rows':23,'ambiguous_rows':4,'abstract_gate_combinations':len(combos),'runtime_faults_executed':False}))

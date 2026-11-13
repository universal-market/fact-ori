"""Static Q8 review binding/expectation checks only; never executes models or a diagnostic harness."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);base=root/'data/W015-Q8-real-model-protocol-v1';p=json.loads((base/'protocol.json').read_text());m=json.loads((base/'review-input.json').read_text());s=json.loads((root/'public/library.json').read_text());prior=json.loads((root/'data/W015-Q7-container-http-v1/results.json').read_text());checks=[]
def check(label,value):
 assert value,label
 checks.append(label)
def sha(raw):return hashlib.sha256(raw).hexdigest()
check('manifest-raw',sha((base/'review-input.json').read_bytes())=='33e6c1cf8f9500f64de65ca07eb91333089898408a1aa0335e915928ef346420')
check('protocol-raw',sha((base/'protocol.json').read_bytes())=='15cf189f478c8448b806340a083f997d3160b3f7f6e827753fd40ac7bc11db88')
check('25bindings',len(m['raw_bindings'])==25)
for path,h in m['raw_bindings'].items():check('raw/'+path,sha((root/path).read_bytes())==h)
check('snapshot-raw',sha((root/p['snapshot']['path']).read_bytes())==p['snapshot']['raw_sha256'])
check('snapshot-import',s['library_import_id']==p['snapshot']['library_import_id'])
check('snapshot-subject',s['snapshot_sha256']==p['snapshot']['subject_sha256'])
check('snapshot-eight-records',len(s['records'])==p['snapshot']['records']==8)
models=json.loads((root/'service/models.json').read_text());check('model-pins-exact',p['model_pins']==models)
names=['engine.mjs','server.mjs','models.json','snapshot-boundary.mjs'];fingerprint=sha('\n'.join((root/'service'/n).read_text() for n in names).encode());check('fingerprint-exact-source',fingerprint==p['engine_fingerprint'])
for key in ['source_commit','candidate_image_id']:check('prior-stub/'+key,p[key]==prior[key])
check('prior-stub/fingerprint',prior['observed']['engine_revision']==p['engine_fingerprint'])
check('prior-stub/only-stub-kind',prior['kind']=='isolated_candidate_HTTP_with_deterministic_stubs')
check('two-cases',len(p['cases'])==2)
for case in p['cases']:
 check(case['id']+'/consent-false',case['input']['public_review'] is False)
 check(case['id']+'/import',case['expected']['import_id']==s['library_import_id'])
c=p['cases'][0];row=next(r for r in s['records'] if r['claim_id']=='C004');e=c['expected'];pkg=row['evidence_package'];check('capital-exact-inspection',e['inspection']=={k:row[k] for k in ['claim_id','version','sha256']});check('capital-version1',row['version']==1)
check('capital-answer',e['answer']==pkg['answer']==row['record']['answer']);check('capital-verdict',e['verdict']==pkg['evidence_verdict']=='supported');check('capital-approved',pkg['state']=='approved');check('capital-package-python-canonical',e['evidence_package_canonical_sha256']==sha(json.dumps(pkg,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()))
check('capital-not-exact-alias',c['input']['text'] not in [x['question'] for x in s['exact_mappings']]);check('unknown-no-active-gold',not any(r['claim_id']=='C012' for r in s['records']))
u=p['cases'][1]['expected'];check('unknown-withholds',u['status']=='not_in_library' and all(u[k] is None for k in ['answer','verdict','job']))
check('proposed-only',p['status']==m['status']=='proposed_not_executed')
x=p['execution'];caps=x['resource_caps'];check('serial',caps['concurrency']==1);check('bounded-time',caps['total_wall_seconds']==600 and caps['startup_wall_seconds']==180 and caps['per_case_wall_seconds']==180);check('phase-budget-slack',caps['total_wall_seconds']-(caps['startup_wall_seconds']+len(p['cases'])*caps['per_case_wall_seconds'])==60);check('no-spend-download',caps['paid_cost']==0 and caps['new_model_download_bytes']==0)
engine=(root/'service/engine.mjs').read_text();check('real-client-300s-vs-phase180s','AbortSignal.timeout(300000)' in engine and caps['per_case_wall_seconds']==180);check('keepalive-needs-container-teardown','keep_alive: "30m"' in engine);check('case-expected-shape-engine-fields',all(k in engine for k in ['query_relationship_review','model_assessed','evidence_package','inspection','import_id','job: null']))
check('protocol-no-runtime-observations','unresolved preflight' in x['cached_model_mount'] or 'later preflight' in x['cached_model_mount']);check('no-execution-before-review','separate recipient assessment' in x['start_condition'])
print(json.dumps({'schema_version':1,'task':'FO-W015-Q8','kind':'static_protocol_review_checks','passed':len(checks),'failed':0,'checks':checks,'limits':'Static binding/internal expectation consistency only. No model/container/cache/mount/headroom/harness/runtime feasibility observed.'},indent=2))

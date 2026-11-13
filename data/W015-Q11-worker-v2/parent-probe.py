"""Actual accepted parent + fixture-only Node worker; no model/Docker/network."""
import hashlib,json,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'scripts'))
from diagnostic_supervisor import supervise
p=json.loads((root/'data/W015-Q8-real-model-protocol-v1/protocol.json').read_text());caps=p['execution']['resource_caps']
phases=[('startup',caps['startup_wall_seconds'])]+[(c['id'],caps['per_case_wall_seconds']) for c in p['cases']]
with tempfile.TemporaryDirectory(prefix='factori-q10-offline-') as d:
 output=Path(d)/'fixture.json'
 receipt=supervise(['node',str(root/'scripts/diagnostic-worker-v2.mjs'),'--fixture',str(output)],phases,total_seconds=caps['total_wall_seconds'])
 assert receipt['status']=='success' and receipt['leader_reaped'] and receipt['within_total_deadline']
 raw=output.read_bytes();report=json.loads(raw)
 assert report['kind']=='actual_engine_offline_fixture_diagnostic' and report['counts']['forbidden_submissions']==0
 assert raw==(root/'data/W015-Q11-worker-v2/fixture-results.json').read_bytes()
 result={'schema_version':1,'task_key':'FO-W015-Q11','kind':'accepted_supervisor_offline_worker_integration','receipt':receipt,'worker_result_raw_sha256':hashlib.sha256(raw).hexdigest(),'observed_worker_node':report['node'],'limits':['Actual local supervised fixture-only worker, no real model/backend/Docker/cache/preflight.','600s configured cap with fast authored workload, not600s workload/resource/production proof.','Uses accepted supervisor unchanged; child result checks and metadata completion remain distinct.']}
 (root/'data/W015-Q11-worker-v2/parent-integration.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'parent_status':receipt['status'],'phases':receipt['completed_phases'],'node':report['node']}))

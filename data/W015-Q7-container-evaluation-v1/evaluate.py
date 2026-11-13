#!/usr/bin/env python3
"""Owner-authorized isolated packaging measurement. No production replacement."""
import hashlib,io,json,subprocess,tarfile,tempfile
from pathlib import Path
SOURCE='9e87c693d25df86b9e5300a9b71dcdaa5a6b372e'
BASE='node@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d'
TAG='factori-q7-candidate:9e87c693d25d'
KEY='W015-Q7-candidate-v1'
PATHS=['.dockerignore','deploy/self-hosted/semantic.Dockerfile','service','public/library.json','public/openapi.json','scripts/semantic-report.mjs','scripts/evaluation-contracts']
def run(args,timeout=120):
 return subprocess.run(args,capture_output=True,text=True,timeout=timeout)
def git(path):return subprocess.check_output(['git','show',SOURCE+':'+path])
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 assert run(['docker','image','inspect',BASE,'--format','{{.Id}}']).returncode==0,'Pinned base not cached; no automatic pull'
 active=run(['docker','ps','-a','--filter','label=factori.evaluation='+KEY,'--format','{{.ID}}']);assert active.returncode==0 and not active.stdout.strip(),'Existing evaluation container; reconcile first'
 existing=run(['docker','image','inspect',TAG,'--format','{{json .Config.Labels}}'])
 tar=subprocess.check_output(['git','archive',SOURCE,*PATHS]);tarhash=sha(tar)
 if existing.returncode==0:
  labels=json.loads(existing.stdout);assert labels.get('factori.evaluation')==KEY and labels.get('org.opencontainers.image.revision')==SOURCE,'Conflicting candidate image'
  built=False
 else:
  with tempfile.TemporaryDirectory(prefix='factori-q7-context-') as directory:
   with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
    for member in archive.getmembers():assert not member.name.startswith('/') and '..' not in Path(member.name).parts
    archive.extractall(directory,filter='data')
   build=run(['docker','build','--pull=false','--network=none','--label','factori.evaluation='+KEY,'--label','org.opencontainers.image.revision='+SOURCE,'-t',TAG,'-f',directory+'/deploy/self-hosted/semantic.Dockerfile',directory])
   assert build.returncode==0,build.stderr[-2000:]
  built=True
 image=run(['docker','image','inspect',TAG,'--format','{{json .Id}}']);assert image.returncode==0;imageid=json.loads(image.stdout)
 flags=['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--label','factori.evaluation='+KEY]
 probe="""import {readFileSync,existsSync} from 'node:fs';import {createHash} from 'node:crypto';
const names=['engine.mjs','server.mjs','models.json','snapshot-boundary.mjs','library.json'];
const files=Object.fromEntries(names.map(p=>[p,existsSync('/app/'+p)?createHash('sha256').update(readFileSync('/app/'+p)).digest('hex'):null]));
let fingerprint=null,import_error=null;try{fingerprint=(await import('./engine.mjs')).engineFingerprint()}catch(e){import_error={code:e.code,message:e.message}}
console.log(JSON.stringify({files,fingerprint,import_error}));"""
 packaged=run([*flags,'--entrypoint','node',imageid,'--input-type=module','-e',probe]);assert packaged.returncode==0,packaged.stderr
 contents=json.loads(packaged.stdout)
 startup=run([*flags,'--tmpfs','/state:rw,noexec,nosuid,size=8m,mode=1777',imageid],timeout=20)
 expected={name:sha(git('service/'+name)) for name in ['engine.mjs','server.mjs','models.json','snapshot-boundary.mjs']};expected['library.json']=sha(git('public/library.json'))
 fingerprint=sha(b'\n'.join(git('service/'+name) for name in ['engine.mjs','server.mjs','models.json','snapshot-boundary.mjs']))
 with tempfile.TemporaryDirectory(prefix='factori-q7-invalid-') as directory:
  invalidpath=Path(directory)/'snapshot.json'
  original=json.loads(git('scripts/fixtures/c007a-v3/pending-consumer-results-v1.json'))['export']
  invalidpath.write_text(json.dumps(original));invalidpath.chmod(0o644)
  rejected=run([*flags,'--tmpfs','/state:rw,noexec,nosuid,size=8m,mode=1777','--mount','type=bind,src='+str(invalidpath)+',dst=/input/snapshot.json,readonly','--env','LIBRARY_PATH=/input/snapshot.json',imageid],timeout=20)
 r={'schema_version':1,'task_key':KEY,'kind':'isolated_candidate_container_packaging_evaluation','source_commit':SOURCE,'base_image':BASE,'candidate_tag':TAG,'candidate_image_id':imageid,'image_built_this_run':built,'build_network':'none','exact_git_archive_paths':PATHS,'archive_raw_sha256':tarhash,'dockerignore_raw_sha256':sha(git('.dockerignore')),'dockerfile_raw_sha256':sha(git('deploy/self-hosted/semantic.Dockerfile')),'expected_file_hashes':expected,'expected_fingerprint':fingerprint,'packaged':contents,'default_startup':{'exit_code':startup.returncode,'stdout':startup.stdout,'error_category':'model_identification_fetch_failed_with_network_none' if 'ModelClient.identify' in startup.stderr else 'unclassified','cause_code':'EAI_AGAIN' if 'EAI_AGAIN' in startup.stderr else None,'raw_stderr_published':False,'interpretation':'Valid snapshot reaches model identification but network-disabled candidate cannot reach inference; not a readiness/HTTP/model verdict.'},'invalid_snapshot_startup':{'exit_code':rejected.returncode,'stdout':rejected.stdout,'stderr':rejected.stderr},'container_limits':{'network':'none','read_only_root':True,'capabilities':'ALL dropped','no_new_privileges':True,'memory':'256m','pids_limit':64,'state':'ephemeral tmpfs, no production mount'},'findings':[],'limits':['Independent owner-authorized engineering evaluation, not extension/reopening/submission of completed Q7 Task.','No production service, port, network, volume, model, credential, notification or schedule changes.','No valid HTTP/model/factual/runtime approval; stop at first packaging/startup failure.','Docker image local content ID is observed, not a signed/reproducible-build attestation.']}
 if contents['files']['snapshot-boundary.mjs'] is None:
  r['findings'].append({'id':'Q7-PKG-F1','severity':'deployment_blocker','observation':'Accepted guard exists in exact source but is omitted from Docker build context by explicit .dockerignore allowlist. COPY service/ does not restore ignored files. Engine import/default startup fails ERR_MODULE_NOT_FOUND for /app/snapshot-boundary.mjs.','missing_review_input':'.dockerignore was not one of18Q7 review-bound files.','disposition':'Source-level structural observations retained; packaging-readiness statement corrected, deployment blocked until separately versioned allowlist fix/actual-image regression/fresh exact packaging review.'})
 if not r['findings']:
  assert contents['import_error'] is None
  assert contents['fingerprint']==fingerprint
  for name in expected:assert contents['files'][name]==expected[name],name
  assert rejected.returncode==1 and 'INVALID_PUBLIC_SNAPSHOT' in rejected.stderr and 'listening' not in rejected.stdout
 r['initial_probe_revision_note']='First unpublished probe assumed missing guard and asserted before saving results. Actual image contained guard. Reconciled existing exact-labeled image; corrected probe records observed results and adds actual container invalid-snapshot case. No source or Dockerignore fix required by measurement.'
 p=Path('data/W015-Q7-container-evaluation-v1/results.json');p.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({'image':imageid,'missing_guard':contents['files']['snapshot-boundary.mjs'] is None,'startup_exit':startup.returncode,'invalid_snapshot_exit':rejected.returncode,'result':'packaging_blocker' if r['findings'] else 'packaging_and_invalid_format_gate_pass' ,'receipt':str(p),'sha256':sha(p.read_bytes())}))
if __name__=='__main__':main()

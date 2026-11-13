#!/usr/bin/env python3
"""Run one bounded isolated candidate HTTP probe; no production mounts/network."""
import hashlib,json,subprocess
from pathlib import Path
IMAGE='sha256:39838c0cf50ea2a4f717ff863bf954f2c16699e70398f3b4d7be1b4f51b0004b'
KEY='W015-Q7-http-v1'
ROOT=Path(__file__).parent

def run(args,**kw):return subprocess.run(args,capture_output=True,text=True,timeout=45,**kw)
def main():
 active=run(['docker','ps','-a','--filter','label=factori.evaluation='+KEY,'--format','{{.ID}}']);assert active.returncode==0 and not active.stdout.strip(),'Existing worker: reconcile before execution'
 image=run(['docker','image','inspect',IMAGE,'--format','{{json .Config.Labels}}']);assert image.returncode==0
 labels=json.loads(image.stdout);assert labels['org.opencontainers.image.revision']=='9e87c693d25df86b9e5300a9b71dcdaa5a6b372e'
 args=['docker','run','--rm','--name','factori-q7-http-v1','-i','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','64','--label','factori.evaluation='+KEY,'--tmpfs','/state:rw,noexec,nosuid,size=8m,mode=1777','--entrypoint','node',IMAGE,'--input-type=module']
 try:
  result=run(args,input=(ROOT/'probe.mjs').read_text())
 except subprocess.TimeoutExpired:
  run(['docker','rm','-f','factori-q7-http-v1']) # only this newly launched probe
  raise
 assert result.returncode==0,result.stderr[-1000:]
 observed=json.loads(next(line.removeprefix('FACT_ORI_RESULT ') for line in result.stdout.splitlines() if line.startswith('FACT_ORI_RESULT ')))
 end=run(['docker','ps','-a','--filter','label=factori.evaluation='+KEY,'--format','{{.ID}}']);assert end.returncode==0 and not end.stdout.strip()
 receipt={'schema_version':1,'task_key':KEY,'kind':'isolated_candidate_HTTP_with_deterministic_stubs','source_commit':labels['org.opencontainers.image.revision'],'candidate_image_id':IMAGE,'probe_raw_sha256':hashlib.sha256((ROOT/'probe.mjs').read_bytes()).hexdigest(),'observed':observed,'container_removed':True,'isolation':{'network':'none; loopback stubs only','root':'read-only','state':'ephemeral tmpfs','ports_published':False,'capabilities':'ALL dropped','no_new_privileges':True,'memory':'256m','pids':64},'roles':{'author_decision_actor_recorder':'@adrian.factomaton','prior_reviewer':'@adrian.factfinder','dependence':'Shared Adrian owner/prior source/design exposure/authored fixtures; no independent-owner/blinded/held-out/non-author curation.'},'limits':['Independent owner-authorized follow-on evaluation; no extension/reopening/submission of completed Q7 Task.','Stub tags claim pinned model digests; no actual model binaries/inference/backend evaluated.','No factual verdict, production readiness/deployment, security/concurrency/resource/restart proof or API publication approval.','No production container, mount, model, credential, notification or schedule changes.']}
 (ROOT/'results.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt['observed']))
if __name__=='__main__':main()

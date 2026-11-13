"""Run permitted offline checks in the isolated Git archive from repository root."""
import pathlib,json,hashlib,subprocess,tempfile
root=pathlib.Path('local/W015-Q11/exact-source').resolve();sha=lambda b:hashlib.sha256(b).hexdigest();manifest=root/'data/W015-Q11-worker-v2/review-input.json';m=json.loads(manifest.read_text());assert sha(manifest.read_bytes())=='734b70a0e38b8e8d98abaaff54f517c3892891f3b4b3b2c4afc9f3a74b0083dc'
for p,h in m['raw_bindings'].items():assert sha((root/p).read_bytes())==h,p
old=json.loads((root/'data/W015-Q10-worker-v1/review-input.json').read_text())['raw_bindings'];assert len(old)==40 and all(m['raw_bindings'][p]==h for p,h in old.items())
def run(args,cwd=root):
 r=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=20);assert r.returncode==0,(args,r.stdout,r.stderr);return {'command':args,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
tests=run(['node','scripts/diagnostic-worker-v2.test.mjs']);assert 'pass 46' in tests['stdout']
reg=run(['node','data/W015-Q11-worker-v2/regression-probes.mjs','.']);assert reg['stdout'].encode()==(root/'data/W015-Q11-worker-v2/regression-results.json').read_bytes()
parent=run(['python','-B','data/W015-Q11-worker-v2/parent-probe.py']);receipt=json.loads((root/'data/W015-Q11-worker-v2/parent-integration.json').read_text());assert receipt['receipt']['leader_reaped']
with tempfile.TemporaryDirectory(prefix='ff-q11-cli-') as d:
 out=pathlib.Path(d)/'report.json';run(['node','scripts/diagnostic-worker-v2.mjs','--fixture',str(out)]);raw=out.read_bytes();assert raw==(root/'data/W015-Q11-worker-v2/fixture-results.json').read_bytes()
 r=subprocess.run(['node','scripts/diagnostic-worker-v2.mjs','--fixture',str(out)],cwd=root,capture_output=True,text=True,timeout=20);assert r.returncode==1 and out.read_bytes()==raw and r.stderr.endswith('DIAGNOSTIC_WORKER_FAILED\n')
 for args in [[],['--live'],['--fixture',str(out),'extra']]:
  r=subprocess.run(['node','scripts/diagnostic-worker-v2.mjs']+args,cwd=root,capture_output=True,text=True,timeout=20);assert r.returncode==2 and not r.stdout
probes=run(['node','data/W015-Q11-factfinder-review-v1/review-probes.mjs',str(root)],pathlib.Path.cwd());p=pathlib.Path('data/W015-Q11-factfinder-review-v1');(p/'probe-results.json').write_text(probes['stdout']);
result={'schema_version':1,'task_key':'FO-W015-Q11','bindings_verified':len(m['raw_bindings']),'prior_bindings_unchanged':40,'raw_bindings':m['raw_bindings'],'supplied_tests':tests,'supplied_regression_probes':reg,'parent_probe':parent,'parent_receipt':receipt,'reviewer_probe_count':json.loads(probes['stdout'])['checks'],'cli_checks':'fresh output byte-equal; overwrite rejected preserving bytes; three invalid argument shapes rejected','limits':'Offline Node25.2.1 public fixtures only. Parent receipt regenerated only in isolated extraction after initial51hash verification. No model/backendHTTP/Convex/Docker/cache/preflight/600s workload/general sanitizer proof.'};(p/'verification-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['bindings_verified','prior_bindings_unchanged','reviewer_probe_count','cli_checks']}))

"""Offline pinned-input and CLI checks. Run from repository root."""
import hashlib,json,pathlib,subprocess,tempfile,shutil
root=pathlib.Path('local/W015-Q10/exact-source').resolve()
sha=lambda b:hashlib.sha256(b).hexdigest()
manifest=root/'data/W015-Q10-worker-v1/review-input.json'
assert sha(manifest.read_bytes())=='30b77c4712eced00970ddf0c87a4e1ca05a6b9cdd2c2954198b85c0a23290fd6'
m=json.loads(manifest.read_text());assert len(m['raw_bindings'])==40
for p,h in m['raw_bindings'].items():assert sha((root/p).read_bytes())==h,p
prior=json.loads((root/'data/W015-Q9-supervisor-v1/review-input.json').read_text())['raw_bindings']
assert len(prior)==31 and all(m['raw_bindings'][p]==h for p,h in prior.items())
checks=[{'name':'40 exact raw bindings and manifest digest','pass':True},{'name':'31 prior bindings unchanged','pass':True}]
def run(args,cwd=root):
 r=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=20)
 return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
tests=run(['node','scripts/diagnostic-worker.test.mjs']);assert tests['returncode']==0 and 'pass 18' in tests['stdout']
parent=run(['python','-B','data/W015-Q10-worker-v1/parent-probe.py']);assert parent['returncode']==0
with tempfile.TemporaryDirectory(prefix='ff-q10-review-') as tmp:
 t=pathlib.Path(tmp);out=t/'out.json'
 a=run(['node','scripts/diagnostic-worker.mjs','--fixture',str(out)]);assert a['returncode']==0
 original=out.read_bytes();assert original==(root/'data/W015-Q10-worker-v1/fixture-results.json').read_bytes()
 b=run(['node','scripts/diagnostic-worker.mjs','--fixture',str(out)]);assert b['returncode']==1 and b['stderr'].endswith('DIAGNOSTIC_WORKER_FAILED\n') and out.read_bytes()==original
 checks.append({'name':'fresh-output wx rejects overwrite preserving original bytes','pass':True})
 for argv in [[],['--live'],['--fixture',str(t/'extra.json'),'extra']]:
  c=run(['node','scripts/diagnostic-worker.mjs']+argv);assert c['returncode']==2 and c['stdout']==''
 checks.append({'name':'three invalid CLI argument shapes rejected','pass':True})
 # Isolated copies exercise pin failures without changing exact-source inputs.
 mini=t/'source';shutil.copytree(root/'service',mini/'service');shutil.copytree(root/'scripts',mini/'scripts')
 (mini/'data/W015-Q8-real-model-protocol-v1').mkdir(parents=True)
 protocol=mini/'data/W015-Q8-real-model-protocol-v1/protocol.json'
 protocol.write_text(json.dumps({'snapshot':{'path':'nonexistent-path'}}))
 c=run(['node','scripts/diagnostic-worker.mjs','--fixture',str(t/'bad.json')],mini)
 assert c['returncode']==1 and 'ENOENT' not in c['stderr'] and not (t/'bad.json').exists()
 checks.append({'name':'altered protocol cannot select alternate snapshot path; fixed CLI failure','pass':True})
 shutil.copy(root/'data/W015-Q8-real-model-protocol-v1/protocol.json',protocol)
 (mini/'public').mkdir();shutil.copy(root/'public/library.json',mini/'public/library.json')
 (mini/'service/models.json').write_text('{}')
 c=run(['node','scripts/diagnostic-worker.mjs','--fixture',str(t/'pins.json')],mini)
 assert c['returncode']==1 and not (t/'pins.json').exists()
 checks.append({'name':'altered model pins fail before report publication','pass':True})
result={'schema_version':1,'task_key':'FO-W015-Q10','bindings':m['raw_bindings'],'checks':checks,'supplied_direct_tests':tests,'supervised_fixture_probe':parent,'limits':['Offline fixture workload only; observed Node v25.2.1, not pinned candidate image.','Protocol-before-path ordering established by code inspection plus altered-protocol failure; fixed error text alone cannot identify internal failing gate.','Parent probe writes its integration receipt within isolated exact-source extraction after initial binding verification.']}
pathlib.Path('data/W015-Q10-factfinder-review-v1/verification-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'bindings':40,'prior_unchanged':31,'direct_tests':18,'parent_success':True,'additional_checks':len(checks)}))

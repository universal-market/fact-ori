import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

source=Path(sys.argv[1]).resolve()
project=Path(sys.argv[2]).resolve()
sys.path.insert(0,str(source/'scripts'))
from review_source_binding import inspect_binding
from review_receipt_store import MAX_BYTES

checks=[]
def check(name,passed):
 assert passed,name
 checks.append({'name':name,'pass':True})
def raw(x):return json.dumps(x).encode()
with tempfile.TemporaryDirectory() as td:
 p=Path(td)
 def git(*args):
  return subprocess.check_output(['git','-C',str(p),*args],stderr=subprocess.PIPE)
 git('init','-q');git('config','user.name','Synthetic Reviewer Fixture');git('config','user.email','fixture@example.invalid')
 f=p/'safe.txt';f.write_bytes(b'original\n');git('add','safe.txt');git('commit','-qm','fixture')
 initial=git('rev-parse','HEAD').decode().strip()
 receipt={'schema_version':1,'artifact_kind':'exact_code_review','reviewed_commit':initial,
          'source_raw_bindings':{'safe.txt':hashlib.sha256(f.read_bytes()).hexdigest()},
          'decision':'accept','authenticated':True}
 invalid=[]
 for field,value in [('schema_version',True),('artifact_kind','other'),('reviewed_commit','HEAD'),('reviewed_commit','-'+'a'*39),('reviewed_commit','A'*40),('source_raw_bindings',{})]:
  x=copy.deepcopy(receipt);x[field]=value;invalid.append((field+repr(value),raw(x)))
 for path in ['', '.', '../safe.txt', '/safe.txt', 'a//b', './safe.txt', 'a/../safe.txt', '.env.local', '.aws/config', 'keys/test.pem', 'safe.txt\x00']:
  x=copy.deepcopy(receipt);x['source_raw_bindings']={path:'0'*64};invalid.append(('path:'+repr(path),raw(x)))
 for digest in ['A'*64,'0'*63,1,None]:
  x=copy.deepcopy(receipt);x['source_raw_bindings']={'safe.txt':digest};invalid.append(('digest:'+repr(digest),raw(x)))
 invalid += [('duplicate',b'{"schema_version":1,"schema_version":1}'),('float',b'{"x":1.0}'),('oversize',b' '*(MAX_BYTES+1))]
 for name,body in invalid:
  with patch('review_source_binding.build_manifest') as build:
   try:inspect_binding(p,body);rejected=False
   except (ValueError,TypeError,RecursionError):rejected=True
   check('reject-before-git:'+name,rejected and build.call_count==0)
 same=inspect_binding(p,raw(receipt))
 check('same-commit-and-byte-match',same['target_relationship']=='same_commit' and same['declared_bindings_match'])
 check('imported-acceptance-does-not-promote',same['receipt_authentication']=='unverified_import' and same['implementation_review']=='pending')
 check('mode-observed',same['checked_bindings'][0]['observed_mode']=='100644')
 pretty=inspect_binding(p,json.dumps(receipt,indent=2).encode())
 check('raw-canonical-domains',pretty['receipt_raw_sha256']!=same['receipt_raw_sha256'] and pretty['receipt_canonical_sha256']==same['receipt_canonical_sha256'])
 x=copy.deepcopy(receipt);x['source_raw_bindings']={'safe.txt':'0'*64,'absent.txt':'1'*64}
 failed=inspect_binding(p,raw(x))
 check('missing-and-mismatch-diagnostics',not failed['declared_bindings_match'] and {x['path']:x['observed_sha256'] for x in failed['checked_bindings']}['absent.txt'] is None)
 git('commit','--allow-empty','-qm','distinct commit identical tree')
 equal=inspect_binding(p,raw(receipt))
 check('distinct-commit-equal-tree',equal['target_relationship']=='same_tree_merge' and equal['reviewed_source']['source_commit']!=equal['target_source']['source_commit'])
 # Mode and new metadata can change target tree without invalidating historical hashes.
 git('update-index','--chmod=+x','safe.txt');git('commit','-qm','mode-only change')
 mode=inspect_binding(p,raw(receipt))
 check('historical-mode-scope-disclosed',mode['target_relationship']=='different_tree' and mode['declared_bindings_match'] and mode['checked_bindings'][0]['observed_mode']=='100644')
 x=copy.deepcopy(receipt);x['reviewed_commit']=git('rev-parse','HEAD').decode().strip()
 executable=inspect_binding(p,raw(x))
 check('executable-reviewed-mode-observed',executable['checked_bindings'][0]['observed_mode']=='100755' and executable['declared_bindings_match'])
 f.write_bytes(b'changed\n');git('add','safe.txt');git('commit','-qm','changed target bytes')
 drift=inspect_binding(p,raw(receipt))
 check('historical-hashes-match-after-target-byte-drift',drift['declared_bindings_match'] and drift['target_relationship']=='different_tree')
 f.write_bytes(b'uncommitted overwrite\n')
 check('working-tree-not-used',inspect_binding(p,raw(receipt))==drift)
 rp=p/'receipt.json';rp.write_bytes(raw(receipt))
 cmd=[sys.executable,'-B',str(source/'scripts/review_source_binding.py'),'--root',str(p),'--receipt',str(rp)]
 cli=subprocess.run(cmd,capture_output=True,check=True)
 check('actual-cli-match',json.loads(cli.stdout)==drift)
 bad=subprocess.run(cmd+['--target-revision','--not-a-revision'],capture_output=True)
 check('cli-invalid-argv-exit2',bad.returncode==2 and bad.stdout==b'')
 # Git replacement refs cannot reinterpret the explicitly named original commit.
 git('replace',initial,git('rev-parse','HEAD').decode().strip())
 replaced=inspect_binding(p,raw(receipt),initial)
 check('replacement-isolation',replaced['target_relationship']=='same_commit' and replaced['declared_bindings_match'] and replaced['reviewed_source']==same['reviewed_source'])

# Real immutable S1 review, actual public project Git objects; no journal mutation.
body=(project/'data/FO-W020-S1-R1-factfinder-review-v1.json').read_bytes()
historic=inspect_binding(project,body,'55d4b8bddf7c8c9cc0f879b412d69f933e116a37')
check('real-S1-five-historical-bindings',historic['declared_bindings_match'] and len(historic['checked_bindings'])==5 and historic['target_relationship']=='same_commit')
target=inspect_binding(project,body,'a11c6a7c8863a490747746520321b97a1e302309')
check('real-S1-historical-matches-distinct-target-tree',target['declared_bindings_match'] and target['target_relationship']=='different_tree')
check('real-S1-no-promotion',target['receipt_authentication']=='unverified_import' and target['implementation_review']=='pending')
print(json.dumps({'reviewed_commit':'a11c6a7c8863a490747746520321b97a1e302309','checks_passed':len(checks),'checks':checks,
 'limits':['Matching declarations are historical byte correspondence, not current target acceptance or complete review coverage.',
 'Modes are observed at reviewed source, not authenticated reviewed mode claims.',
 'Audited public Git workflow only; no crash/race/malicious-repository or exhaustive resource/security proof.']},indent=2))

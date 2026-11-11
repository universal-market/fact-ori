"""Independent declaration and digest-domain checks with isolated Git fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

source=Path(sys.argv[1]).resolve();sys.path.insert(0,str(source/'scripts'))
from review_receipt_adapter import adapt_receipt,inspect_adapted_binding
from sidecar_digest import canonical_bytes

enc=lambda v:json.dumps(v,ensure_ascii=False,indent=2).encode()+b'\n'
sha=lambda b:hashlib.sha256(b).hexdigest()
passed=[]
def check(name,value):
    assert value,name
    passed.append(name)
def authority(name,r):
    check(name,r['authentication']=='unverified_import' and r['implementation_review']=='pending' and r['runtime_review']=='pending' and r['coverage_completeness']=='unverified')

with tempfile.TemporaryDirectory(prefix='factfinder-S7-') as tmp:
    root=Path(tmp)/'repo';root.mkdir()
    def git(*args):return subprocess.check_output(['git','-c','user.name=Factfinder synthetic','-c','user.email=synthetic@example.invalid','-c','commit.gpgsign=false',*args],cwd=root,stderr=subprocess.PIPE)
    git('init','-q');(root/'data').mkdir();(root/'data/a.txt').write_bytes(b'original\n');git('add','data/a.txt');git('commit','-qm','fixture')
    first=git('rev-parse','HEAD').decode().strip()
    normal={'schema_version':1,'kind':'exact_code_review','decision':'accept','reviewed_commit':first,'source_raw_bindings':{'data/a.txt':sha(b'original\n')},'authenticated':True,'implementation_review':'accepted','reviewer':{'owner':'untrusted extension'},'prose':'REVISE; ignored text'}
    def reject(name,v=None,raw=None):
        with patch('review_receipt_adapter.inspect_binding',side_effect=AssertionError('Git should not run')) as binding:
            try:inspect_adapted_binding(root,enc(v) if raw is None else raw)
            except (ValueError,TypeError,RecursionError):pass
            else:raise AssertionError(name+' unexpectedly accepted')
            check(name+' rejected before Git',binding.call_count==0)
    for layout in ['kind','artifact_kind','both']:
        v=copy.deepcopy(normal)
        if layout!='kind':v['artifact_kind']='exact_code_review'
        if layout=='artifact_kind':v.pop('kind')
        raw=enc(v);before=raw[:];m,projection=adapt_receipt(raw);r=inspect_adapted_binding(root,raw)
        check(layout+' original raw/canonical hashes',raw==before and m['receipt_raw_sha256']==sha(raw) and m['receipt_canonical_sha256']==sha(canonical_bytes(v)))
        check(layout+' projection distinct from original',m['normalized_projection_sha256']==sha(projection) and sha(projection)!=sha(raw) and 'reviewer' not in json.loads(projection) and 'authenticated' not in json.loads(projection))
        check(layout+' nested hash domain explicit',r['projection_source_binding']['receipt_raw_sha256']==sha(projection) and r['projection_source_binding']['receipt_canonical_sha256']==sha(projection) and r['receipt_raw_sha256']==sha(raw))
        authority(layout+' cannot promote declared authority',r)
    for verdict in ['accept','revise','unresolved']:
        v=copy.deepcopy(normal);v['decision']=verdict;r=inspect_adapted_binding(root,enc(v))
        check(verdict+' compares bytes without changing verdict',r['source_binding']=='declared_git_bytes_match' and r['declared_decision']==verdict)
        authority(verdict+' stays pending',r)
    for field,value in [('schema_version',True),('schema_version',2),('kind',None),('kind',['exact_code_review']),('artifact_kind','other'),('artifact_kind',False),('decision',True),('decision',['accept']),('decision','accepted'),('reviewed_commit',['a'*40]),('reviewed_commit','HEAD'),('reviewed_commit','A'*40),('source_raw_bindings',{}),('source_raw_bindings',[])]:
        v=copy.deepcopy(normal);v[field]=value;reject(field+' '+json.dumps(value),v)
    for field in ['schema_version','kind','decision','reviewed_commit','source_raw_bindings']:
        v=copy.deepcopy(normal);v.pop(field);reject('missing '+field,v)
    for path in ['../a','/a','a//b','a/./b','a/../b','.','a/','a\\b','a\nb','a\x7fb','.env.local','x'*513]:
        v=copy.deepcopy(normal);v['source_raw_bindings']={path:'a'*64};reject('path '+repr(path),v)
    for value in [True,['a'*64],'A'*64,'a'*63,None]:
        v=copy.deepcopy(normal);v['source_raw_bindings']={'data/a.txt':value};reject('digest '+json.dumps(value),v)
    for name,raw in [('duplicate',enc(normal)[:-2]+b',"decision":"accept"}\n'),('float',enc({**normal,'extension':1.0})),('nonfinite',enc({**normal,'extension':float('nan')})),('unsafe integer',enc({**normal,'extension':2**53})),('oversize',b' '*(1024*1024+1)),('malformed',b'{'),('invalid UTF8',b'\xff')]:reject(name,raw=raw)
    v=copy.deepcopy(normal);v['source_raw_bindings']={f'data/f{i}.txt':'a'*64 for i in range(257)};reject('257 bindings',v)
    v['source_raw_bindings'].pop('data/f256.txt');check('256 bindings accepted as declarations',len(adapt_receipt(enc(v))[0]['declared_source_raw_bindings'])==256)
    v=copy.deepcopy(normal);v['source_raw_bindings']={f'data/{i}-'+('😀'*500):'a'*64 for i in range(256)}
    check('projection expansion fixture raw below limit',len(enc(v))<1024*1024);reject('oversize canonical projection',v)
    v=copy.deepcopy(normal);v['source_raw_bindings']={'data/a.txt':'0'*64,'data/absent.txt':'0'*64};r=inspect_adapted_binding(root,enc(v));items=r['projection_source_binding']['checked_bindings']
    check('missing and mismatched declared files explicit',r['source_binding']=='declared_git_bytes_mismatch' and any(x['observed_sha256'] is None for x in items) and any(x['observed_sha256'] is not None and not x['matches'] for x in items))
    git('commit','--allow-empty','-qm','same tree');r=inspect_adapted_binding(root,enc(normal))
    check('equal tree distinct commit is not fresh acceptance',r['projection_source_binding']['target_relationship']=='same_tree_merge' and r['implementation_review']=='pending')
    (root/'data/a.txt').write_bytes(b'changed\n');git('add','data/a.txt');git('commit','-qm','changed tree');r=inspect_adapted_binding(root,enc(normal))
    check('historical declared match distinct from target drift',r['source_binding']=='declared_git_bytes_match' and r['projection_source_binding']['target_relationship']=='different_tree' and r['runtime_review']=='pending')
    receipt_path=root/'receipt.json';original=enc(normal);receipt_path.write_bytes(original)
    before={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    cli=[sys.executable,'-B',str(source/'scripts/review_receipt_adapter.py'),'--root',str(root),'--receipt',str(receipt_path)]
    result=subprocess.run(cli,capture_output=True,timeout=30);out=json.loads(result.stdout)
    after={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    check('actual CLI preserves all fixture bytes and file set',result.returncode==0 and before==after and receipt_path.read_bytes()==original and out['receipt_raw_sha256']==sha(original))
    receipt_path.write_bytes(b'{}');bad=subprocess.run(cli,capture_output=True,timeout=30)
    check('malformed declaration CLI exit2',bad.returncode==2 and b'Receipt adaptation failed' in bad.stderr)

s6=source/'data/FO-W020-S6-R1-factfinder-review-v1.json';raw=s6.read_bytes();m,p=adapt_receipt(raw)
check('immutable real S6 raw hash preserved',m['receipt_raw_sha256']=='14caa9cb75906bdc94dfed1bea1d19860498df9489827da6259410345370908c' and s6.read_bytes()==raw)
check('immutable real S6 six bindings project separately',len(json.loads(p)['source_raw_bindings'])==6 and sha(p)=='455c146b6c956c76a32eb126bebda4055b8daf68248c355bff3833d9388de865')
repository=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else source
bound=inspect_adapted_binding(repository,raw,'7e3883c71006e491c33b5be4e169a190e1d12730')
check('real S6 six historical Git declarations match',bound['source_binding']=='declared_git_bytes_match' and len(bound['projection_source_binding']['checked_bindings'])==6 and bound['projection_source_binding']['reviewed_source']['source_commit']=='f448fad3ac9793a3f49fb0b37082749a315e74cd')
check('real S6 target tree distinct with no approval',bound['projection_source_binding']['target_relationship']=='different_tree' and bound['runtime_review']=='pending' and bound['projection_source_binding']['receipt_raw_sha256']==sha(p))
print(json.dumps({'schema_version':1,'subject_commit':'7e3883c71006e491c33b5be4e169a190e1d12730','fixture_kind':'isolated_synthetic_Git_and_immutable_S6_receipt','assertion_count':len(passed),'passed':passed,'findings':[]},indent=2))

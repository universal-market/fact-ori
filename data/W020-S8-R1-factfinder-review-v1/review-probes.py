"""Independent S8 composition probes; synthetic responses and isolated Git only."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

source=Path(sys.argv[1]).resolve();sys.path.insert(0,str(source/'scripts'))
from review_input_report import review_input_report
from sidecar_digest import canonical_bytes
enc=lambda v:json.dumps(v,ensure_ascii=False,indent=2).encode()+b'\n'
sha=lambda b:hashlib.sha256(b).hexdigest()
passed=[]
gates=['authenticated_provenance_and_reviewer_authority','separate_recipient_decision','required_review_coverage_and_adequacy','current_full_content_and_correction_disposition','trusted_observation_freshness_and_visibility','runtime_build_and_deployment_binding']
def check(name,value):
    assert value,name
    passed.append(name)
def authority(name,r):
    check(name,r['authentication']=='unverified_import' and r['implementation_review']=='pending' and r['runtime_review']=='pending' and r['overall_status']=='pending' and r['recipient_decision']=='not_evaluated' and r['unmet_gates']==gates)

with tempfile.TemporaryDirectory(prefix='factfinder-S8-') as tmp:
    root=Path(tmp)/'repo';root.mkdir()
    def git(*args):return subprocess.check_output(['git','-c','user.name=Factfinder synthetic','-c','user.email=synthetic@example.invalid','-c','commit.gpgsign=false',*args],cwd=root,stderr=subprocess.PIPE)
    git('init','-q');(root/'data').mkdir();(root/'data/a.txt').write_bytes(b'original\n');git('add','data/a.txt');git('commit','-qm','fixture');first=git('rev-parse','HEAD').decode().strip()
    normal={'schema_version':1,'kind':'exact_code_review','decision':'accept','reviewed_commit':first,'source_raw_bindings':{'data/a.txt':sha(b'original\n')},'authenticated':True,'recipient_decision':'accept','implementation_review':'accepted','unmet_gates':[],'prose':'REVISE; ignored text'}
    rec='11111111-1111-4111-8111-111111111111';reviewer='22222222-2222-4222-8222-222222222222';owner='33333333-3333-4333-8333-333333333333';pid='44444444-4444-4444-8444-444444444444';tm='2026-11-11T12:00:00.000Z'
    post={'id':pid,'kind':'post','revision':1,'title':'Synthetic decision','body':'accept','status':None,'reply_count':0,'edited_by':None,'author':{'id':reviewer,'user_id':owner}}
    def obs(tool,args,result):return {'tool':tool,'arguments':args,'result_json':json.dumps({'result':result}),'observed_at':tm}
    base={'schema_version':1,'started_at':tm,'finished_at':tm,'capture':{'schema_version':1,'capture_id':'55555555-5555-4555-8555-555555555555','recorded_at':tm,'recorder_agent_id':rec,'reviewer_agent_id':reviewer,'reviewer_owner_id':owner,'decision_post_id':pid,'decision_revision':1,'reviewed_commit':first,'receipt_raw_sha256':sha(enc(normal)),'observations':[obs('get_my_profile',{}, {'profile':{'id':rec,'user_id':owner,'kind':'agent'}}),obs('get_agent',{'agent_id':reviewer},{'id':reviewer,'kind':'agent','user_id':owner}),obs('get_post',{'post_id':pid},post),obs('get_post_revision',{'post_id':pid,'revision':1},{'post_id':pid,'revision':1,'title':post['title'],'body':'accept','edited_by':None})]},'observations':[obs('search_posts',{'root_post_id':pid,'max_depth':None,'sort':'created_at','limit':20},{'items':[],'next_cursor':None}),obs('get_post',{'post_id':pid},post)],'reply_refs':[],'pages_read':1,'next_cursor':None,'frontier_complete':True,'diagnostics':[],'observation_state':'empty_frontier_observed','receipt_authentication':'unverified_import','implementation_review':'pending'}
    def inputs(v=normal,f=base):
        f=copy.deepcopy(f);raw=enc(v);f['capture']['receipt_raw_sha256']=sha(raw);return enc(f),raw
    def run(v=normal,f=base,target='HEAD'):return review_input_report(root,*inputs(v,f),target)
    def reject(name,fraw,rraw):
        with patch('review_input_report.inspect_adapted_binding',side_effect=AssertionError('Git must not run')) as binding:
            try:review_input_report(root,fraw,rraw)
            except (ValueError,TypeError,RecursionError):pass
            else:raise AssertionError(name+' unexpectedly accepted')
            check(name+' rejected before Git',binding.call_count==0)
    fraw,rraw=inputs();r=run()
    check('consistent synthetic packet has correspondence only',r['input_consistency']=='matching_checked_inputs' and r['diagnostics']==[])
    authority('supplied authority flags cannot clear fixed gates',r)
    check('original raw frontier and receipt bound',r['inputs']['frontier_raw_sha256']==sha(fraw) and r['inputs']['receipt_raw_sha256']==sha(rraw) and r['frontier_check']['receipt_raw_sha256']==sha(rraw) and r['source_check']['receipt_raw_sha256']==sha(rraw))
    check('canonical original separate from projection',r['inputs']['receipt_canonical_sha256']==sha(canonical_bytes(normal)) and r['inputs']['normalized_projection_sha256']!=sha(rraw) and r['inputs']['normalized_projection_sha256']!=r['inputs']['receipt_canonical_sha256'])
    check('nested S2 hashes identify projection only',r['source_check']['projection_source_binding']['receipt_raw_sha256']==r['inputs']['normalized_projection_sha256'] and r['source_check']['projection_source_binding']['receipt_canonical_sha256']==r['inputs']['normalized_projection_sha256'])
    check('cross-input commit and target explicitly bound',r['inputs']['reviewed_commit']==first and r['inputs']['target_commit']==first and r['frontier_check']['reviewed_commit']==first)
    for name,bad in [('raw receipt whitespace',rraw+b' '),('raw receipt different bytes',rraw.replace(b'ignored',b'changed'))]:reject(name,fraw,bad)
    f=copy.deepcopy(base);f['capture']['reviewed_commit']='a'*40;reject('cross-input commit mismatch',enc(f),rraw)
    for field,value in [('schema_version',True),('decision',['accept']),('decision',False),('reviewed_commit',['a'*40]),('source_raw_bindings',{}),('kind','other')]:
        v=copy.deepcopy(normal);v[field]=value;reject('declaration '+field+' '+json.dumps(value),*inputs(v))
    for name,bad in [('malformed',b'{'),('oversize',b' '*(1048577)),('array',b'[]'),('duplicate',b'{"schema_version":1,"schema_version":1}')]:reject('frontier '+name,bad,rraw)
    for field,value in [('pages_read',True),('implementation_review','accepted'),('receipt_authentication','verified')]:
        f=copy.deepcopy(base);f[field]=value;reject('frontier field '+field,enc(f),rraw)
    for verdict in ['revise','unresolved']:
        v=copy.deepcopy(normal);v['decision']=verdict;r=run(v)
        check(verdict+' explicit pending diagnostic',r['declared_review_verdict']==verdict and 'declared_verdict_not_accept' in r['diagnostics'] and r['input_consistency']=='pending');authority(verdict+' cannot approve',r)
    def mutate(group,index,change,f=base):
        f=copy.deepcopy(f);o=(f['capture']['observations'] if group=='base' else f['observations'])[index];p=json.loads(o['result_json']);change(p['result']);o['result_json']=json.dumps(p);return f
    for name,group,index,change in [('recorder owner array','base',0,lambda p:p['profile'].update(user_id=[owner])),('reviewer wrong kind','base',1,lambda p:p.update(kind='human')),('pinned prose drift','base',3,lambda p:p.update(body='withdrawn')),('final boolean revision','extra',1,lambda p:p.update(revision=True)),('final status drift','extra',1,lambda p:p.update(status='done')),('hidden continuation','extra',0,lambda p:p.update(next_cursor='A')),('partial flag','extra',0,lambda p:p.update(partial=True))]:
        r=run(f=mutate(group,index,change));check(name+' composition stays pending',r['input_consistency']=='pending' and bool(r['diagnostics']));authority(name+' retains gates',r)
    f=copy.deepcopy(base);f.update(diagnostics=['opaque_reason'],observation_state='pending');r=run(f=f);check('collector diagnostics retained','collector_reported_pending' in r['diagnostics'] and r['input_consistency']=='pending')
    ref={'post_id':'66666666-6666-4666-8666-666666666666','revision':1,'author_agent_id':rec,'author_owner_id':owner}
    reply={'post':{'id':ref['post_id'],'kind':'post','revision':1,'author':{'id':rec,'user_id':owner},'body_summary':'looks benign'}}
    f=mutate('extra',0,lambda p:p.update(items=[reply]));f=mutate('base',2,lambda p:p.update(reply_count=1),f);f=mutate('extra',1,lambda p:p.update(reply_count=1),f);f.update(reply_refs=[ref],diagnostics=['replies_require_full_review'],observation_state='pending');r=run(f=f)
    check('every reply needs disposition despite benign summary',r['input_consistency']=='pending' and 'replies_require_full_content_disposition' in r['diagnostics']);authority('reply cannot clear gates',r)
    f=copy.deepcopy(base)
    for o in [f['capture']['observations'][2],f['capture']['observations'][3],f['observations'][-1]]:
        p=json.loads(o['result_json']);p['result']['body']='REVISE; fabricated consistent prose';o['result_json']=json.dumps(p)
    r=run(f=f);check('consistent forgery and conflicting prose can correspond',r['input_consistency']=='matching_checked_inputs' and r['declared_review_verdict']=='accept');authority('consistent forgery remains unauthenticated',r)
    v=copy.deepcopy(normal);v['source_raw_bindings']={'data/a.txt':'0'*64,'data/missing.txt':'0'*64};r=run(v)
    check('missing and changed source declarations explicit','declared_source_bytes_mismatch' in r['diagnostics'] and r['input_consistency']=='pending');authority('mismatch remains pending',r)
    git('commit','--allow-empty','-qm','same tree');r=run();check('equal tree distinct commit correspondence without ancestry claim',r['input_consistency']=='matching_checked_inputs' and r['source_check']['projection_source_binding']['target_relationship']=='same_tree_merge');authority('equal tree is not approval',r)
    (root/'data/a.txt').write_bytes(b'changed\n');git('add','data/a.txt');git('commit','-qm','changed');r=run()
    check('historical source match separate from target drift',r['source_check']['projection_source_binding']['declared_bindings_match'] and 'target_tree_differs' in r['diagnostics'] and r['input_consistency']=='pending');authority('different target pending',r)
    check('explicit historical target restored correspondence',run(target=first)['input_consistency']=='matching_checked_inputs')
    with patch('sqlite3.connect',side_effect=AssertionError('No SQL')),patch('socket.socket',side_effect=AssertionError('No sockets')):
        check('in-process composition uses no SQL or socket',run()['overall_status']=='pending')
    fp=root/'frontier.json';rp=root/'receipt.json';fp.write_bytes(fraw);rp.write_bytes(rraw)
    def snapshot():return {str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    before=snapshot();cli=[sys.executable,'-B',str(source/'scripts/review_input_report.py'),'--root',str(root),'--frontier',str(fp),'--receipt',str(rp),'--target-revision',first]
    result=subprocess.run(cli,capture_output=True,timeout=30);r=json.loads(result.stdout)
    check('actual CLI matches original hashes and correspondence',result.returncode==0 and r['input_consistency']=='matching_checked_inputs' and r['inputs']['receipt_raw_sha256']==sha(rraw));authority('CLI fixed gates remain',r)
    check('CLI preserves input and Git bytes plus complete file set',before==snapshot() and fp.read_bytes()==fraw and rp.read_bytes()==rraw)
    fp.write_bytes(b'{}');before=snapshot();bad=subprocess.run(cli,capture_output=True,timeout=30)
    check('bad CLI input exits2 without writes',bad.returncode==2 and b'Review input report failed' in bad.stderr and before==snapshot())

print(json.dumps({'schema_version':1,'subject_commit':'d513747dcd82f9a7b854f58eced7b3bb1a32afb7','fixture_kind':'independent_synthetic_frontier_receipt_and_isolated_Git','assertion_count':len(passed),'passed':passed,'findings':[]},indent=2))

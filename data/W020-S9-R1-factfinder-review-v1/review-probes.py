"""Independent offline S9 boundary probes using public synthetic declarations."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

source=Path(sys.argv[1]).resolve();sys.path.insert(0,str(source/'scripts'))
import review_reply_disposition as subject
from sidecar_digest import canonical_bytes
D=source/'data/W020-E1-F1-factfinder-design-v1'
base=json.loads((D/'example.synthetic.json').read_bytes());obs=json.loads((D/'observations.synthetic.json').read_bytes())
enc=lambda v:json.dumps(v,ensure_ascii=True,indent=2).encode()+b'\n'
sha=lambda b:hashlib.sha256(b).hexdigest()
passed=[]
def check(name,value):
    assert value,name
    passed.append(name)
def run(d=base,o=obs):return subject.reply_disposition_report(enc(d),enc(o))
def fixed(name,r,o=obs):
    check(name,r['authentication']=='unverified_import' and r['recipient_decision']=='not_evaluated' and all(r[k]=='pending' for k in ['implementation_review','runtime_review','overall_status']) and r['coverage_evidence']=='unchecked_imported_assertions' and r['unmet_gates']==list(subject.GATES) and r['collector_diagnostics']==o['collector_diagnostics'] and r['author_withdrawal_established'] is False)
def invalid(name,d=base,o=obs):
    r=run(d,o);check(name+' invalidated',r['outcome']=='invalidated');fixed(name+' fixed pending output',r,o)
def rejected(name,raw,side='disposition'):
    args=(raw,enc(obs)) if side=='disposition' else (enc(base),raw)
    try:subject.reply_disposition_report(*args)
    except (ValueError,RecursionError):check(name+' rejects',True)
    else:raise AssertionError(name+' accepted')
def mutate(v,path,value):
    v=copy.deepcopy(v);n=v
    for key in path[:-1]:n=n[key]
    n[path[-1]]=value;return v

r=run();check('positive correspondence',r['outcome']=='corresponding_nonblocking_declaration');fixed('positive is never approval',r)
check('own author versus separate recorder explicit',r['same_owner'] is True and r['decision_actor_is_reply_author']==[True] and r['recorder_is_decision_actor']==[False])
for name,raw in [('duplicate',b'{"x":1,"x":2}'),('fraction',b'{"x":1.0}'),('exponent',b'{"x":1e0}'),('nonfinite',b'{"x":Infinity}'),('portable overflow',b'{"x":9007199254740992}'),('negative overflow',b'{"x":-9007199254740992}'),('invalid UTF8',b'\xff'),('truncated',b'{'),('oversize',b' '*(1048577))]:
    for side in ['disposition','observations']:rejected(name+' '+side,raw,side)
for raw in [b'null',b'[]',b'true',b'1',b'"text"']:
    invalid('wrong disposition root '+raw.decode(),json.loads(raw));rejected('wrong observation root '+raw.decode(),raw,'observations')
for field in ['frontier_complete','full_content_available','correction_chain_complete','caller_age_bound_satisfied']:
    for value in [1,'true',None,[]]:rejected(field+' type '+json.dumps(value),enc(mutate(obs,[field],value)),'observations')
    invalid(field+' false',o=mutate(obs,[field],False))
for field in ['receipt_raw_sha256','frontier_raw_sha256','capture_id','reviewed_commit','target_commit']:
    value='d'*40 if 'commit' in field else 'd'*64 if 'sha256' in field else '66666666-6666-4666-8666-666666666666'
    invalid('one-sided '+field,mutate(base,['bindings',field],value))
for path,value,name in [(['parent','revision'],2,'parent revision'),(['parent','body_sha256'],'d'*64,'parent body'),(['entries',0,'reply','revision'],2,'reply revision'),(['entries',0,'reply','title_sha256'],'d'*64,'reply title'),(['entries',0,'reply','body_sha256'],'d'*64,'reply body'),(['entries',0,'reply','edited_by'],base['reviewer'],'reply editor'),(['entries',0,'reply','status'],'closed','reply status'),(['entries',0,'reply','parent_post_id'],None,'reply reparent'),(['entries',0,'rationale'],'  ','blank rationale'),(['coverage','checked'],[],'checked list'),(['coverage','unchecked'],[],'gate list'),(['entries',0,'decision_actor','owner_id'],'44444444-4444-4444-8444-444444444444','actor owner drift')]:invalid(name,mutate(base,path,value))
for value in [True,0,-1,'1',None,[]]:invalid('revision '+json.dumps(value),mutate(base,['entries',0,'reply','revision'],value))
rejected('revision portable overflow',enc(mutate(base,['entries',0,'reply','revision'],9007199254740992)))
o=copy.deepcopy(obs);o['known_actors'].append(copy.deepcopy(o['known_actors'][0]));rejected('duplicate same owner actor',enc(o),'observations')
o=copy.deepcopy(obs);a=copy.deepcopy(o['known_actors'][0]);a['owner_id']='44444444-4444-4444-8444-444444444444';o['known_actors'].append(a);rejected('conflicting actor owner',enc(o),'observations')
for field,count in [('replies',257),('corrections',257),('known_actors',1025)]:
    value=[obs['known_actors'][0]]*count if field=='known_actors' else [obs['replies'][0]]*count
    rejected(field+' count limit',enc(mutate(obs,[field],value)),'observations')
for field in obs:
    o=copy.deepcopy(obs);del o[field];rejected('missing observation '+field,enc(o),'observations')
o=copy.deepcopy(obs);o['trusted']=True;rejected('extra observation authority field',enc(o),'observations')
for field,value in [('authentication','verified'),('recipient_decision','accept'),('implementation_review','accepted'),('runtime_review','accepted'),('overall_status','accepted')]:invalid('supplied '+field,mutate(base,[field],value))
for classification in ['material_objection','correction','withdrawal']:
    d=mutate(base,['entries',0,'classification'],classification);d['entries'][0]['affected_targets']=[{k:base['parent'][k] for k in ['post_id','revision','body_sha256']}]
    r=run(d);check(classification+' requires reopen',r['outcome']=='reopen_required');fixed(classification+' does not establish withdrawal authority',r)
r=run(mutate(base,['entries',0,'classification'],'unresolved'));check('unresolved holds',r['outcome']=='hold_unresolved');fixed('unresolved retains original diagnostics',r)
o=copy.deepcopy(obs);d=copy.deepcopy(base);o['replies'][0]['body_sha256']='e'*64;d['entries'][0]['reply']['body_sha256']='e'*64;d['coverage']['reply_set_sha256']=sha(canonical_bytes(o['replies']));r=run(d,o);check('coherent forged body correspondence remains possible',r['outcome']=='corresponding_nonblocking_declaration');fixed('coherent forgery does not authenticate',r,o)
o=copy.deepcopy(obs);d=copy.deepcopy(base)
for field in ['frontier_complete','full_content_available','correction_chain_complete','caller_age_bound_satisfied']:o[field]=True
r=run(d,o);check('self-declared checked coverage never becomes evidence',r['coverage_evidence']=='unchecked_imported_assertions')
raw=enc(base);compact=json.dumps(base,sort_keys=True,separators=(',',':')).encode();oraw=enc(obs);ocompact=json.dumps(obs,separators=(',',':')).encode()
a=subject.reply_disposition_report(raw,oraw);b=subject.reply_disposition_report(compact,ocompact)
check('both original raw hash domains bind bytes',a['inputs']['disposition_raw_sha256']==sha(raw) and a['inputs']['observations_raw_sha256']==sha(oraw) and a['inputs']['disposition_raw_sha256']!=b['inputs']['disposition_raw_sha256'] and a['inputs']['observations_raw_sha256']!=b['inputs']['observations_raw_sha256'])
check('both canonical hash domains stable under whitespace',a['inputs']['disposition_canonical_sha256']==b['inputs']['disposition_canonical_sha256']==sha(canonical_bytes(base)) and a['inputs']['observations_canonical_sha256']==b['inputs']['observations_canonical_sha256']==sha(canonical_bytes(obs)))
with patch('sqlite3.connect',side_effect=AssertionError('No SQL')),patch('socket.socket',side_effect=AssertionError('No sockets')):fixed('no SQL/socket in process',run())
with tempfile.TemporaryDirectory(prefix='factfinder-S9-') as tmp:
    root=Path(tmp);schema=root/'schema.json';schema.write_bytes(subject.SCHEMA_PATH.read_bytes()+b' ')
    with patch.object(subject,'SCHEMA_PATH',schema):
        try:run()
        except ValueError:check('changed pinned schema rejected',True)
        else:raise AssertionError('schema tamper accepted')
    dp=root/'disposition.json';op=root/'observations.json';dp.write_bytes(raw);op.write_bytes(oraw)
    def snapshot():return {p.name:sha(p.read_bytes()) for p in root.iterdir() if p.is_file()}
    before=snapshot();cli=[sys.executable,'-B',str(source/'scripts/review_reply_disposition.py'),'--disposition',str(dp),'--observations',str(op)]
    result=subprocess.run(cli,capture_output=True,timeout=30);r=json.loads(result.stdout);check('actual CLI correspondence',result.returncode==0 and r['outcome']=='corresponding_nonblocking_declaration');fixed('CLI remains pending',r)
    check('CLI preserves complete file set and all input bytes',before==snapshot() and dp.read_bytes()==raw and op.read_bytes()==oraw)
    op.write_bytes(b'{"x":1,"x":2}');before=snapshot();bad=subprocess.run(cli,capture_output=True,timeout=30);check('bad CLI exit2 with empty stdout and no mutation',bad.returncode==2 and bad.stdout==b'' and b'Reply disposition report failed' in bad.stderr and before==snapshot())

print(json.dumps({'schema_version':1,'subject_commit':'d6460658cdc30aaf73907be59811a205b29b54c4','fixture_kind':'public_synthetic_declarations_and_isolated_CLI_schema_tamper_fixture','assertion_count':len(passed),'passed':passed,'findings':[]},indent=2))

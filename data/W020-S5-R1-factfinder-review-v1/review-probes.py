"""Independent bounded validator/storage probes on exact extracted source."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'scripts'))
from review_frontier_store import frontier_metadata,store_frontier
from review_receipt_store import MAX_BYTES,store_capture

generated=json.loads(subprocess.check_output(['node',str(Path(__file__).with_suffix('.mjs')),str(root)],timeout=30))
normal=generated['envelope'];receipt=generated['receipt'].encode()
encode=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
raw=encode(normal)
passed=[]
def check(name,condition):
    assert condition,name
    passed.append(name)
def variant(path,value):
    obj=copy.deepcopy(normal);parent=obj
    for part in path[:-1]:parent=parent[part]
    parent[path[-1]]=value
    return obj

with tempfile.TemporaryDirectory(prefix='factfinder-S5-') as tmp:
    tmp=Path(tmp)
    def reject(name,obj=None,packet=None,receipt_bytes=receipt):
        database=tmp/'invalid.sqlite'
        try:store_frontier(database,encode(obj) if packet is None else packet,receipt_bytes)
        except (ValueError,TypeError,RecursionError):pass
        else:raise AssertionError(name+' unexpectedly accepted')
        check(name+' rejects before database creation',not database.exists())
    cases=[
        ('extra envelope field',['extra'],1),('bool schema',['schema_version'],True),
        ('bool pages',['pages_read'],True),('oversize pages',['pages_read'],11),
        ('negative pages',['pages_read'],-1),('numeric completion',['frontier_complete'],1),
        ('array cursor',['next_cursor'],[]),('oversize cursor',['next_cursor'],'x'*8001),
        ('empty cursor',['next_cursor'],''),('complete nonnull cursor',['next_cursor'],'next'),
        ('authority label',['receipt_authentication'],'authenticated'),
        ('accepted implementation',['implementation_review'],'accepted'),
        ('unknown observation state',['observation_state'],'accepted'),
        ('empty diagnostic',['diagnostics'],['']),('oversize diagnostic',['diagnostics'],['x'*201]),
        ('too many diagnostics',['diagnostics'],['x']*65),
        ('empty base prefix',['capture','observations'],[]),
        ('wrong base tool',['capture','observations',0,'tool'],'get_post'),
        ('bool revision argument',['capture','observations',3,'arguments','revision'],True),
        ('wrong search root',['observations',0,'arguments','root_post_id'],'66666666-6666-4666-8666-666666666666'),
        ('limited search depth',['observations',0,'arguments','max_depth'],1),
        ('bool search depth',['observations',0,'arguments','max_depth'],False),
        ('extra first cursor',['observations',0,'arguments','cursor'],'unexpected'),
        ('write tool',['observations',1,'tool'],'create_post'),
        ('extra final read argument',['observations',1,'arguments','extra'],1),
        ('wrong page count',['pages_read'],2),
        ('invalid calendar',['finished_at'],'2026-02-30T00:00:00Z'),
        ('offset UTC spelling',['finished_at'],'2026-11-11T03:00:00+00:00'),
        ('fraction precision',['finished_at'],'2026-11-11T03:00:00.1234Z'),
        ('missing finish',['finished_at'],None),
        ('start capture mismatch',['started_at'],'2000-01-01T00:00:00Z'),
        ('old base observation',['capture','observations',0,'observed_at'],'2000-01-01T00:00:00Z'),
        ('future frontier observation',['observations',0,'observed_at'],'2099-01-01T00:00:00Z'),
        ('bool capture revision',['capture','decision_revision'],True),
        ('array UUID',['capture','capture_id'],[normal['capture']['capture_id']]),
        ('wrong raw binding',['capture','receipt_raw_sha256'],'c'*64),
    ]
    for name,path,value in cases:reject(name,variant(path,value))
    reject('wrong receipt bytes',normal,receipt_bytes=receipt+b' ')
    reject('outer duplicate key',packet=raw[:-1]+b',"pages_read":1}')
    reject('outer fractional number',packet=raw.replace(b'"pages_read":1',b'"pages_read":1.0'))
    reject('outer oversize',packet=b' '*(MAX_BYTES+1))
    for name,result in [('nested duplicate','{"x":1,"x":2}'),('nested malformed','{'),('nested array','[]'),('nested NaN','{"x":NaN}')]:
        reject(name,variant(['observations',0,'result_json'],result))
    expanded=variant(['observations',0,'result_json'],json.dumps({'x':'é'*180000},ensure_ascii=False))
    check('canonical expansion fixture raw below cap',len(encode(expanded))<MAX_BYTES)
    reject('canonical expansion exceeds cap',expanded)
    ref={'post_id':'66666666-6666-4666-8666-666666666666','revision':1,'author_agent_id':normal['capture']['reviewer_agent_id'],'author_owner_id':normal['capture']['reviewer_agent_id']}
    for label,refs in [('duplicate refs',[ref,ref]),('root ref',[{**ref,'post_id':normal['capture']['decision_post_id']}]),('bool ref revision',[{**ref,'revision':True}]),('too many refs',[ref]*201)]:
        obj=copy.deepcopy(normal);obj.update(reply_refs=refs,diagnostics=['requires_full_review'],observation_state='pending');reject(label,obj)
    ordered=copy.deepcopy(normal)
    ordered['started_at']=ordered['capture']['recorded_at']='2026-11-11T00:00:00.000Z'
    ordered['finished_at']='2026-11-11T00:00:01.000Z'
    for obs in ordered['capture']['observations']+ordered['observations']:obs['observed_at']='2026-11-11T00:00:00.500Z'
    ordered['capture']['observations'][0]['observed_at']='2026-11-11T00:00:00.800Z'
    reject('in-interval out-of-order timestamps',ordered)
    continued=copy.deepcopy(normal)
    continued['observations'].insert(1,copy.deepcopy(continued['observations'][0]))
    continued['pages_read']=2
    reject('missing continuation cursor',continued)
    partial=copy.deepcopy(normal);partial.update(frontier_complete=False,next_cursor='resume',diagnostics=['budget_exhausted'],observation_state='pending')
    m=frontier_metadata(encode(partial),receipt)
    check('partial envelope retained pending',m['frontier_verification']=='pending')
    access=copy.deepcopy(partial);access['observations']=access['observations'][:1];access['observations'][0]['result_json']='{"error":"DENIED"}'
    check('access failure retained unverified',frontier_metadata(encode(access),receipt)['authentication']=='unverified_import')
    forged=copy.deepcopy(normal)
    for obs in forged['capture']['observations']+forged['observations']:obs['result_json']='{}'
    m=frontier_metadata(encode(forged),receipt)
    check('forged structurally valid observations gain no authority',m['authentication']=='unverified_import' and m['owner_relationship']=='unknown' and m['source_binding']=='unchecked' and m['frontier_verification']=='pending' and m['implementation_review']=='pending')
    database=tmp/'valid.sqlite';m=store_frontier(database,raw,receipt)
    check('real S4 output accepted only as unverified',m['frontier']['observation_state']=='empty_frontier_observed' and m['frontier_verification']=='pending')
    check('identical retry returns identical metadata',store_frontier(database,raw,receipt)==m)
    with sqlite3.connect(database) as db:
        check('exact envelope and receipt bytes retained',db.execute('SELECT frontier_raw,receipt_raw FROM review_frontiers').fetchall()==[(raw,receipt)])
    try:store_frontier(database,json.dumps(normal,indent=2).encode(),receipt)
    except ValueError:pass
    else:raise AssertionError('raw reformat conflict')
    with sqlite3.connect(database) as db:check('raw conflict preserves original row',db.execute('SELECT frontier_raw FROM review_frontiers').fetchall()==[(raw,)])
    store_capture(database,encode(normal['capture']),receipt)
    with sqlite3.connect(database) as db:check('S1 and S5 tables coexist separately',set(x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'"))=={'review_captures','review_frontiers'})
    fp=tmp/'frontier.json';rp=tmp/'receipt.json';fp.write_bytes(raw);rp.write_bytes(receipt)
    cli=[sys.executable,'-B',str(root/'scripts/review_frontier_store.py'),'--database',str(tmp/'processes.sqlite'),'--frontier',str(fp),'--receipt',str(rp)]
    processes=[subprocess.Popen(cli,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(4)]
    outputs=[p.communicate(timeout=30) for p in processes]
    check('four concurrent CLI processes succeed',all(p.returncode==0 for p in processes))
    check('concurrent CLI output identical',all(json.loads(out)==json.loads(outputs[0][0]) for out,err in outputs))
    with sqlite3.connect(tmp/'processes.sqlite') as db:check('concurrent inserts retain one exact row',db.execute('SELECT frontier_raw,receipt_raw FROM review_frontiers').fetchall()==[(raw,receipt)])
    fp.write_bytes(b'{')
    bad=subprocess.run(cli,capture_output=True,timeout=30)
    check('actual CLI malformed input exit2',bad.returncode==2 and b'Frontier storage failed' in bad.stderr)

print(json.dumps({'schema_version':1,'subject_commit':'669c0db90c7805298bfd53d935c25898caa2558e','fixture_kind':'synthetic_real_S4_output_and_isolated_SQLite','assertion_count':len(passed),'passed':passed,'findings':[]},indent=2))

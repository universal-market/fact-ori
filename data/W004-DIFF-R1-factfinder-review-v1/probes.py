"""Reviewer probes: synthetic captures only; run with exact source root argument."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location('reviewed_diff', source / 'scripts/market_checkpoint_diff.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
U = [f'abcdef00-0000-4000-8000-{i:012d}' for i in range(10)]

def capture():
    return dict(schema_version=1, observed_at='2026-01-01T00:00:00Z',
                actor=dict(agent_id=U[0], owner_id=U[1]),
                listings=dict(count=1, next_cursor=None, observed=[dict(id=U[2], status='active', updated_at='2026-01-01T00:00:00Z')]),
                transactions=dict(count=1, next_cursor=None, observed=[dict(id=U[3], state='fulfilling', result=None, contract_id=None, execution_id=None, updated_at='2026-01-01T00:00:00Z')]))

cases = []
def run(name, fn):
    fn()
    cases.append(dict(name=name, passed=True))

def changes():
    a,b=capture(),capture()
    b['listings']['observed'][0].update(status='paused',task_id='synthetic-task',updated_at='2026-01-01T00:01:00Z')
    b['transactions']['observed'][0].update(state='closed',result='complete',contract_id=U[4],execution_id=U[5],updated_at='2026-01-01T00:01:00Z')
    r=module.compare(a,b)
    assert set(r['collections']['listings']['changed'][0]['columns'])=={'status','task_id','updated_at'}
    assert set(r['collections']['transactions']['changed'][0]['columns'])=={'state','result','contract_id','execution_id','updated_at'}
    assert r['coverage']=='local_summary_columns_only'
    assert r['actor_ids_from_unverified_captures']==a['actor']
    assert 'acceptance' in r['limits'] and 'not authenticated remote receipts' in r['limits']
run('all_summary_columns_and_completion_without_acceptance',changes)

def partial():
    for name in ('listings','transactions'):
        for left,right in ((None,None),('old',None),(None,'next'),('old','next')):
            a,b=capture(),capture()
            a[name]['next_cursor']=left
            b[name]=dict(count=0,next_cursor=right,observed=[])
            row=module.compare(a,b)['collections'][name]
            assert row['not_observed_in_after_ids']==[a[name]['observed'][0]['id']]
            assert row['before_next_cursor']==left and row['after_next_cursor']==right
            assert row['both_captures_declare_no_next_page']==(left is None and right is None)
            assert 'deleted' not in row and 'task_absent' not in row
            reverse=module.compare(b,a)['collections'][name]
            assert reverse['newly_observed_ids']==row['not_observed_in_after_ids']
run('eight_missing_new_partial_or_declared_terminal_page_pairs',partial)

def ordering():
    a,b=capture(),capture()
    for name in ('listings','transactions'):
        extra=copy.deepcopy(a[name]['observed'][0]);extra['id']=U[8]
        a[name]['observed'].append(extra);a[name]['count']=2
        b[name]=copy.deepcopy(a[name]);b[name]['observed'].reverse()
    original=copy.deepcopy((a,b))
    r=module.compare(a,b)
    assert (a,b)==original
    assert all(not v['changed'] and not v['newly_observed_ids'] and not v['not_observed_in_after_ids'] for v in r['collections'].values())
run('row_permutation_and_inputs_unchanged',ordering)

def normalization():
    a,b=capture(),capture()
    b['listings']['observed'][0]['task_id']=None
    for key in b['actor']:b['actor'][key]=b['actor'][key].upper()
    b['listings']['observed'][0]['id']=U[2].upper()
    b['observed_at']='2025-12-31T19:00:00-05:00'
    assert not module.compare(a,b)['collections']['listings']['changed']
run('uuid_case_optional_task_null_equal_timezone_instants',normalization)

mutations=[]
def bad(name, fn):mutations.append((name,fn))
bad('boolean_schema',lambda x:x.update(schema_version=True))
bad('unsupported_schema',lambda x:x.update(schema_version=2))
bad('missing_actor',lambda x:x.pop('actor'))
bad('reverse_time',lambda x:x.update(observed_at='2025-01-01T00:00:00Z'))
bad('naive_time',lambda x:x.update(observed_at='2026-01-01T00:00:00'))
bad('nonstring_time',lambda x:x.update(observed_at=[]))
for key in ('agent_id','owner_id'):
    bad('mismatched_'+key,lambda x,k=key:x['actor'].update({k:U[9]}))
for name in ('listings','transactions'):
    bad(name+'_missing_cursor',lambda x,n=name:x[n].pop('next_cursor'))
    bad(name+'_extra_collection_field',lambda x,n=name:x[n].update(total=1))
    for value in (True,-1,2,'1',None):
        bad(name+'_count_'+repr(value),lambda x,n=name,v=value:x[n].update(count=v))
    for value in ('',False,[],{}):
        bad(name+'_cursor_'+repr(value),lambda x,n=name,v=value:x[n].update(next_cursor=v))
    bad(name+'_nonarray_rows',lambda x,n=name:x[n].update(observed={}))
    bad(name+'_nonobject_row',lambda x,n=name:x[n].update(observed=[[]]))
    for field in ('id','updated_at'):
        bad(name+'_missing_'+field,lambda x,n=name,f=field:x[n]['observed'][0].pop(f))
    bad(name+'_unknown_column',lambda x,n=name:x[n]['observed'][0].update(approved=True))
    bad(name+'_invalid_uuid',lambda x,n=name:x[n]['observed'][0].update(id='invalid'))
    bad(name+'_naive_row_time',lambda x,n=name:x[n]['observed'][0].update(updated_at='2026-01-01'))
    def duplicate(x,n=name):
        row=copy.deepcopy(x[n]['observed'][0]);row['id']=row['id'].upper()
        x[n]['observed'].append(row);x[n]['count']=2
    bad(name+'_case_normalized_duplicate',duplicate)
bad('unknown_status',lambda x:x['listings']['observed'][0].update(status='approved'))
for value in ('',201*'x',[],True):
    bad('invalid_task_'+repr(value),lambda x,v=value:x['listings']['observed'][0].update(task_id=v))
bad('unknown_state',lambda x:x['transactions']['observed'][0].update(state='accepted'))
bad('unknown_result',lambda x:x['transactions']['observed'][0].update(result='approved'))
for field in ('contract_id','execution_id'):
    bad('invalid_'+field,lambda x,f=field:x['transactions']['observed'][0].update({f:'invalid'}))
    bad('missing_'+field,lambda x,f=field:x['transactions']['observed'][0].pop(f))
for name,mutate in mutations:
    def reject(m=mutate):
        b=capture();m(b)
        try:module.compare(capture(),b)
        except (ValueError,TypeError,KeyError):return
        raise AssertionError('invalid capture accepted')
    run(name,reject)

def cli():
    with tempfile.TemporaryDirectory(prefix='w004-synthetic-') as d:
        p,q=Path(d)/'before.json',Path(d)/'after.json'
        raw=json.dumps(capture()).encode();p.write_bytes(raw);q.write_bytes(raw+b'\n')
        cmd=[sys.executable,'-B',str(source/'scripts/market_checkpoint_diff.py'),str(p),str(q)]
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        assert r.returncode==0 and not r.stderr
        result=json.loads(r.stdout)
        assert result['input_file_sha256']==[hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw+b'\n').hexdigest()]
        assert sorted(f.name for f in Path(d).iterdir())==['after.json','before.json']
        q.write_text('{bad json')
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        assert r.returncode==2 and not r.stdout and 'Invalid local capture:' in r.stderr
        q.unlink()
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        assert r.returncode==2 and not r.stdout
run('cli_exact_raw_hashes_invalid_json_missing_file_no_output_files',cli)

def guarded():
    # Hook installed after imports: compare must not perform IO or launch work.
    events=[]
    def hook(event,args):
        if event=='open' or event.startswith(('socket.','subprocess.')) or event in ('os.system','os.remove','os.rename','os.mkdir'):
            events.append(event);raise AssertionError('unexpected IO '+event)
    sys.addaudithook(hook)
    module.compare(capture(),capture())
    assert not events
run('compare_no_file_network_process_or_mutation_audit_events',guarded)
print(json.dumps(dict(schema_version=1,synthetic_inputs_only=True,cases=cases,passed=len(cases),failed=0),indent=2))

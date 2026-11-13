"""Finite offline local-child supervisor probes; no models/network/containers."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'scripts'))
from diagnostic_supervisor import supervise
phases=[('first',.3),('second',.3)];checks=[]
def emit(n):return 'print('+repr(json.dumps({'event':'phase_complete','phase':n}))+',flush=True)'
first=emit('first');second=emit('second')
def run(label,source,status,completed,**kw):
 opts=dict(total_seconds=1.5,cleanup_seconds=.3,exit_seconds=.15,output_limit=8192);opts.update(kw)
 r=supervise([sys.executable,'-B','-c',source],phases,**opts)
 assert r['status']==status,(label,r)
 assert r['completed_phases']==completed,(label,r)
 assert r['leader_reaped'] is True and r['within_total_deadline'] is True,(label,r)
 assert r['raw_output_published'] is False
 encoded=json.dumps(r);assert 'UNTRUSTED_CHILD_MARKER' not in encoded
 for stream in ['stdout','stderr']:
  assert set(r['output'][stream])=={'observed_bytes','observed_sha256'}
  assert len(r['output'][stream]['observed_sha256'])==64
 checks.append({'id':label,'status':r['status'],'completed_phases':r['completed_phases'],'leader_reaped':r['leader_reaped'],'within_total_deadline':r['within_total_deadline']})
 return r
run('ordered-success',first+'\n'+second,'success',['first','second'])
for label,payload in [('out-of-order',json.dumps({'event':'phase_complete','phase':'second'})),('unknown-phase',json.dumps({'event':'phase_complete','phase':'other'})),('wrong-event',json.dumps({'event':'reset','phase':'first'})),('extra-key',json.dumps({'event':'phase_complete','phase':'first','answer':'UNTRUSTED_CHILD_MARKER'})),('not-object','[]'),('invalid-json','UNTRUSTED_CHILD_MARKER'),('blank-line','')]:
 run(label,'print('+repr(payload)+',flush=True)','invalid_event',[])
run('repeat-after-transition',first+'\n'+first,'invalid_event',['first'])
run('extra-after-final',first+'\n'+second+'\n'+first,'invalid_event',['first','second'])
run('unterminated-tail',first+'\n'+second+'\nimport sys;sys.stdout.write("UNTRUSTED_CHILD_MARKER");sys.stdout.flush()','incomplete',['first','second'])
run('nonzero-after-final',first+'\n'+second+'\nraise SystemExit(4)','child_failed',['first','second'])
run('closed-pipes-hang-after-final',first+'\n'+second+'\nimport os,time;os.close(1);os.close(2);time.sleep(20)','exit_timeout',['first','second'])
run('stderr-does-not-reset-phase','import sys,time;sys.stderr.write("UNTRUSTED_CHILD_MARKER");sys.stderr.flush();time.sleep(20)','phase_timeout',[])
run('second-phase-hang',first+'\nimport time;time.sleep(20)','phase_timeout',['first'])
run('work-deadline-reserve','import time;time.sleep(20)','total_timeout',[],total_seconds=.4,cleanup_seconds=.25)
r=run('bounded-stderr-prefix','import os;os.write(2,b"x"*100000)','output_limit',[],output_limit=128)
assert r['output']['stderr']['observed_bytes']<=128+4096
r=run('stderr-hash-and-no-raw','import sys;sys.stderr.write("UNTRUSTED_CHILD_MARKER");sys.stderr.flush()\n'+first+'\n'+second,'success',['first','second'])
assert r['output']['stderr']['observed_sha256']==hashlib.sha256(b'UNTRUSTED_CHILD_MARKER').hexdigest()
# Launch failure must be metadata-only, without publishing argv/error text.
r=supervise(['/nonexistent/UNTRUSTED_CHILD_MARKER'],phases,total_seconds=1,cleanup_seconds=.2)
assert r['status']=='supervisor_error' and r['leader_reaped'] is None and 'UNTRUSTED_CHILD_MARKER' not in json.dumps(r);checks.append({'id':'missing-executable-metadata-only','status':r['status']})
for i,kw in enumerate([{'cleanup_seconds':2,'total_seconds':1},{'exit_seconds':True},{'output_limit':127},{'total_seconds':float('inf')} ]):
 try:supervise(['/must-not-launch'],phases,**kw)
 except ValueError:checks.append({'id':f'invalid-limit-{i}','status':'rejected'})
 else:raise AssertionError(kw)
print(json.dumps({'schema_version':1,'task':'FO-W015-Q9','passed':len(checks),'failed':0,'cases':checks,'limits':'Finite scaled POSIX child probes only; no model semantic proof, Docker cleanup, escaped descendant/general reap, process-creation/OS scheduling or600s workload guarantee.'},indent=2))

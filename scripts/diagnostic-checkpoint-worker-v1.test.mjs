import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,chmodSync,rmSync,readFileSync,readdirSync,writeFileSync,lstatSync,symlinkSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {createCheckpointSession,runOfflineCheckpoints} from './diagnostic-checkpoint-worker-v1.mjs';
import {runOffline,validateCase,compact,loadInputs} from './diagnostic-worker-v2.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
const workerSha256=sha(readFileSync(new URL('./diagnostic-checkpoint-worker-v1.mjs',import.meta.url)));
const fixture=await runOffline();
const options=directory=>({directory,runId:'a'.repeat(32),implementationCommit:'b'.repeat(40),workerSha256});
const fresh=()=>{const d=mkdtempSync(join(tmpdir(),'factori-q14-'));chmodSync(d,0o700);return d;};
function using(fn){const d=fresh();try{return fn(d);}finally{rmSync(d,{recursive:true,force:true});}}
test('actual offline engine renames both validated envelopes before their events',async()=>{
 const d=fresh();try{
  const phases=[];const report=await runOfflineCheckpoints(options(d),e=>{
   phases.push(e.phase);
   if(e.phase!=='startup')assert.ok(readdirSync(d).includes(e.phase==='capital-paraphrase'?'01-capital.json':'02-unknown.json'));
  });
  assert.deepEqual(phases,['startup','capital-paraphrase','unknown-no-consent']);assert.equal(report.saved.length,2);
  assert.equal(report.counts.forbidden_submissions,0);
  for(const [i,name]of ['01-capital.json','02-unknown.json'].entries()){
   const b=readFileSync(join(d,name)),e=JSON.parse(b);assert.equal(b.length,report.saved[i].bytes);assert.equal(sha(b),report.saved[i].sha256);
   assert.deepEqual(Object.keys(e).sort(),['schema_version','run_id','case_id','ordinal','input_sha256','implementation_commit','worker_raw_sha256','import_id','result'].sort());
   assert.equal(e.schema_version,1);assert.equal(e.run_id,'a'.repeat(32));assert.equal(e.implementation_commit,'b'.repeat(40));assert.equal(e.worker_raw_sha256,workerSha256);assert.equal(e.ordinal,i+1);
   assert.equal(e.input_sha256,sha(compact(loadInputs().protocol.cases[i].input)));assert.equal(e.import_id,fixture.import_id);assert.equal(validateCase(e.case_id,e.result),true);
   assert.equal(lstatSync(join(d,name)).mode&0o777,0o600);
  }
  assert.equal(readdirSync(d).filter(n=>n.endsWith('.tmp')).length,0);
 }finally{rmSync(d,{recursive:true,force:true});}
});
test('failure after first commit leaves first final file without second',async()=>{
 const d=fresh();try{
  await assert.rejects(runOfflineCheckpoints(options(d),e=>{if(e.phase==='capital-paraphrase')throw new Error('private sentinel');}),/^Error: CHECKPOINT_WORKER_FAILED$/);
  assert.deepEqual(readdirSync(d),['01-capital.json']);assert.equal(validateCase('capital-paraphrase',JSON.parse(readFileSync(join(d,'01-capital.json'))).result),true);
 }finally{rmSync(d,{recursive:true,force:true});}
});
test('out of order, invalid result and serialization replacement never create final file',()=>{
 for(const kind of ['order','invalid','serialization'])using(d=>{
  const s=createCheckpointSession(options(d));const bad=structuredClone(fixture.results[0].result);bad.answer='wrong';
  const r=structuredClone(fixture.results[0].result);r.toJSON=()=>bad;
  assert.throws(()=>kind==='order'?s.commit('unknown-no-consent',fixture.results[1].result):s.commit('capital-paraphrase',kind==='invalid'?bad:r),/^Error: CHECKPOINT_WORKER_FAILED$/);
  assert.deepEqual(readdirSync(d),[]);
  assert.throws(()=>s.commit('capital-paraphrase',fixture.results[0].result),'failure makes session terminal');
 });
});
test('oversized otherwise-valid extension is rejected before file creation',()=>using(d=>{
 const s=createCheckpointSession(options(d)),r=structuredClone(fixture.results[0].result);r.extra='X'.repeat(262144);assert.throws(()=>s.commit('capital-paraphrase',r));assert.deepEqual(readdirSync(d),[]);
}));
test('preexisting final is not overwritten',()=>using(d=>{
 const s=createCheckpointSession(options(d));writeFileSync(join(d,'01-capital.json'),'preserve');assert.throws(()=>s.commit('capital-paraphrase',fixture.results[0].result));assert.equal(readFileSync(join(d,'01-capital.json'),'utf8'),'preserve');
}));
test('preexisting temporary symlink is not followed',()=>using(d=>{
 const s=createCheckpointSession(options(d)),target=join(d,'target');writeFileSync(target,'preserve');symlinkSync(target,join(d,'01-capital.json.tmp'));assert.throws(()=>s.commit('capital-paraphrase',fixture.results[0].result));assert.equal(readFileSync(target,'utf8'),'preserve');assert.equal(readdirSync(d).includes('01-capital.json'),false);
}));
test('repeated first case never overwrites committed bytes',()=>using(d=>{
 const s=createCheckpointSession(options(d));s.commit('capital-paraphrase',fixture.results[0].result);const before=readFileSync(join(d,'01-capital.json'));assert.throws(()=>s.commit('capital-paraphrase',fixture.results[0].result));assert.deepEqual(readFileSync(join(d,'01-capital.json')),before);
}));
test('caller pins, directory freshness/mode and run shape are checked before writes',()=>using(d=>{
 for(const override of [{workerSha256:'0'.repeat(64)},{runId:'../bad'},{implementationCommit:'main'},{directory:'.'}])assert.throws(()=>createCheckpointSession({...options(d),...override}));
 chmodSync(d,0o755);assert.throws(()=>createCheckpointSession(options(d)));chmodSync(d,0o700);writeFileSync(join(d,'old'),'old');assert.throws(()=>createCheckpointSession(options(d)));
}));

import assert from 'node:assert/strict';import fs from 'node:fs';import {syncBuiltinESMExports} from 'node:module';import {join,resolve} from 'node:path';import {tmpdir} from 'node:os';import {pathToFileURL} from 'node:url';import {createHash} from 'node:crypto';
const root=resolve(process.argv[2]),url=p=>pathToFileURL(join(root,p)),sha=b=>createHash('sha256').update(b).digest('hex');
const {runOfflineCheckpoints}=await import(url('scripts/diagnostic-checkpoint-worker-v1.mjs'));
const {observeCheckpoint}=await import(url('scripts/diagnostic-checkpoint-observation-v2.mjs'));
const {reconcileCheckpointPrefix:map}=await import(url('scripts/diagnostic-checkpoint-prefix-v1.mjs'));
const {validateCheckpointBytes:validate}=await import(url('scripts/diagnostic-checkpoint-binding-v1.mjs'));
const directory=fs.mkdtempSync(join(tmpdir(),'factfinder-q20-')),original=fs.readFileSync;
const o={leaderReaped:true,runId:'9'.repeat(32),implementationCommit:'a'.repeat(40),workerSha256:sha(original(url('scripts/diagnostic-checkpoint-worker-v1.mjs')))},checks=[];
const check=(name,fn)=>{fn();checks.push({name,result:'pass'});};
try{
 await runOfflineCheckpoints({directory,...o});const b=[1,2].map(ordinal=>observeCheckpoint({leaderReaped:true,directory,ordinal,readBytes:true}).bytes),digests=b.map(sha);
 const plain=()=>b.map(bytes=>({status:'present',bytes})),baseline=map(plain(),o),target=url('data/W015-Q15-checkpoint-reader-v1/review-input.json').href;
 check('actual producer/observer baseline validates both cases',()=>assert.deepEqual(baseline.map(x=>x.state),['validated','validated']));
 for(const code of ['EIO','EMFILE','ENOMEM','ENOENT','EINTR',null])for(const failAt of [1,2,3])check(`phase-attributed failure ${code??'untyped'} position${failAt}`,()=>{
  let ordinal=0,reads=0,trace=[],rows,err;const obs=b.map((bytes,i)=>({status:'present',get bytes(){ordinal=i+1;return bytes;}}));
  try{fs.readFileSync=(path,...args)=>{if(String(path)===target){reads++;const inBinder=new Error().stack.includes('validateCheckpointBytes');trace.push({ordinal,inBinder});if(reads===failAt)throw code===null?null:{code,message:'PRIVATE'};}return original(path,...args);};syncBuiltinESMExports();try{rows=map(obs,o);}catch(e){err=e.message;}}
  finally{fs.readFileSync=original;syncBuiltinESMExports();}
  assert.deepEqual(trace,Array.from({length:failAt},(_,i)=>({ordinal:i,inBinder:i>0})));
  if(failAt===1){assert.equal(err,'CHECKPOINT_PREFIX_INVALID');assert.equal(rows,undefined);}else{assert.equal(err,undefined);assert.deepEqual(rows.map(x=>x.state),failAt===2?['rejected','rejected']:['validated','rejected']);assert.deepEqual(rows.map(x=>x.reason_code),failAt===2?['checkpoint_invalid','checkpoint_order_invalid']:['validated_match','checkpoint_invalid']);assert.equal(rows[1].validated_projection,null);if(failAt===3)assert.deepEqual(rows[0],baseline[0]);}
 });
 check('direct malformed content and dependency failure same fixed error',()=>{let content,dep;try{validate(Buffer.from('{'),{...o,ordinal:1});}catch(e){content=e.message;}try{fs.readFileSync=(path,...args)=>{if(String(path)===target)throw {code:'EIO'};return original(path,...args);};syncBuiltinESMExports();try{validate(b[0],{...o,ordinal:1});}catch(e){dep=e.message;}}finally{fs.readFileSync=original;syncBuiltinESMExports();}assert.equal(content,'CHECKPOINT_BINDING_INVALID');assert.equal(dep,content);});
 check('baseline target call trace proves read order without injecting failure',()=>{let reads=0;try{fs.readFileSync=(path,...args)=>{if(String(path)===target)reads++;return original(path,...args);};syncBuiltinESMExports();assert.deepEqual(map(plain(),o),baseline);assert.equal(reads,3);}finally{fs.readFileSync=original;syncBuiltinESMExports();}});
 check('restoration identity and actual checkpoint bytes unchanged',()=>{assert.equal(fs.readFileSync,original);const after=[1,2].map(ordinal=>observeCheckpoint({leaderReaped:true,directory,ordinal,readBytes:true}).bytes);assert.deepEqual(after.map(sha),digests);assert.deepEqual(map(after.map(bytes=>({status:'present',bytes})),o),baseline);});
}finally{fs.readFileSync=original;syncBuiltinESMExports();fs.rmSync(directory,{recursive:true,force:true});}
check('owned fixture removed after completion',()=>assert.equal(fs.existsSync(directory),false));
fs.writeFileSync(process.argv[3],JSON.stringify({schema_version:1,passed:checks.length,failed:0,node:process.version,checks,scope:'Controlled dependency-read injection plus in-memory ordinal getter and stack boolean for phase attribution; raw traces/paths/checkpoints/errors not published. Narrow target, not exhaustive failure taxonomy.'},null,2)+'\n');console.log(JSON.stringify({passed:checks.length,failed:0}));

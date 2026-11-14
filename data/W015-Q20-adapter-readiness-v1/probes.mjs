// Offline adapter-readiness investigation: no production adapter or validator changes.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {syncBuiltinESMExports} from 'node:module';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const root=resolve(process.argv[2]),url=p=>pathToFileURL(join(root,p));
const {runOfflineCheckpoints}=await import(url('scripts/diagnostic-checkpoint-worker-v1.mjs'));
const {observeCheckpoint}=await import(url('scripts/diagnostic-checkpoint-observation-v2.mjs'));
const {reconcileCheckpointPrefix}=await import(url('scripts/diagnostic-checkpoint-prefix-v1.mjs'));
const {validateCheckpointBytes}=await import(url('scripts/diagnostic-checkpoint-binding-v1.mjs'));
const sha=b=>createHash('sha256').update(b).digest('hex');
const directory=fs.mkdtempSync(join(tmpdir(),'factori-q20-'));
const options={leaderReaped:true,runId:'f'.repeat(32),implementationCommit:'0ed017800b6a336d488d01511cff4b9e3872be93',workerSha256:sha(fs.readFileSync(url('scripts/diagnostic-checkpoint-worker-v1.mjs')))};
const cases=[];
const summary=rows=>rows.map(x=>({case_id:x.case_id,state:x.state,reason_code:x.reason_code,projection_present:x.validated_projection!==null}));
try{
 await runOfflineCheckpoints({directory,...options});
 const observations=[1,2].map(ordinal=>observeCheckpoint({leaderReaped:true,directory,ordinal,readBytes:true}));
 assert.ok(observations.every(x=>x.status==='present'));
 const baseline=reconcileCheckpointPrefix(observations,options);assert.deepEqual(baseline.map(x=>x.state),['validated','validated']);
 cases.push({name:'actual offline producer + observer + prefix baseline',result:'pass',rows:summary(baseline)});
 // One target read occurs in Q17's precheck before Q16 repeats it.
 const target='/data/W015-Q15-checkpoint-reader-v1/review-input.json';
 for(const code of ['EIO','EMFILE','ENOMEM'])for(const failAt of [1,2,3]){
  const original=fs.readFileSync;let targetReads=0,caught=null,rows=null;
  try{fs.readFileSync=(path,...args)=>{if(String(path).endsWith(target)&&++targetReads===failAt)throw Object.assign(Error('PRIVATE_PATH'),{code});return original(path,...args);};syncBuiltinESMExports();
   try{rows=reconcileCheckpointPrefix(observations,options);}catch(e){caught=e.message;}
  }finally{fs.readFileSync=original;syncBuiltinESMExports();}
  assert.equal(targetReads>=failAt,true);
  if(failAt===1){assert.equal(caught,'CHECKPOINT_PREFIX_INVALID');assert.equal(rows,null);}
  else if(failAt===2){assert.equal(caught,null);assert.deepEqual(rows.map(x=>x.state),['rejected','rejected']);assert.deepEqual(rows.map(x=>x.reason_code),['checkpoint_invalid','checkpoint_order_invalid']);}
  else{assert.equal(caught,null);assert.deepEqual(rows.map(x=>x.state),['validated','rejected']);assert.deepEqual(rows.map(x=>x.reason_code),['validated_match','checkpoint_invalid']);}
  cases.push({name:`controlled dependency ${code} target read ${failAt}`,result:'pass',target_reads:targetReads,thrown_fixed_error:caught,rows:rows?summary(rows):null,whole_result_returned:rows!==null});
 }
 // Direct Q16 content failure and dependency failure expose identical fixed messages.
 let contentError,dependencyError;try{validateCheckpointBytes(Buffer.from('invalid'),{...options,ordinal:1});}catch(e){contentError=e.message;}
 const original=fs.readFileSync;try{fs.readFileSync=(path,...args)=>{if(String(path).endsWith(target))throw {code:'EIO'};return original(path,...args);};syncBuiltinESMExports();try{validateCheckpointBytes(observations[0].bytes,{...options,ordinal:1});}catch(e){dependencyError=e.message;}}finally{fs.readFileSync=original;syncBuiltinESMExports();}
 assert.equal(contentError,'CHECKPOINT_BINDING_INVALID');assert.equal(dependencyError,contentError);
 cases.push({name:'direct binding content/dependency errors indistinguishable',result:'pass',content_error:contentError,dependency_error:dependencyError});
 // No injected failure changed source/checkpoint bytes.
 const after=[1,2].map(ordinal=>observeCheckpoint({leaderReaped:true,directory,ordinal,readBytes:true}));assert.deepEqual(after.map(x=>sha(x.bytes)),observations.map(x=>sha(x.bytes)));assert.deepEqual(reconcileCheckpointPrefix(after,options),baseline);
 cases.push({name:'restored functions + unchanged checkpoints recover baseline',result:'pass',rows:summary(baseline)});
}finally{fs.rmSync(directory,{recursive:true,force:true});}
const result={schema_version:1,task_key:'FO-W015-Q20',kind:'offline_adapter_dependency_failure_investigation',node:process.version,passed:cases.length,failed:0,cases,conclusion:'Q17 precheck failure escalates, but later ordinary dependency read failures inside Q16 become checkpoint_invalid and can retain earlier validated output. Q16 direct error hides dependency/content distinction. Adapter integration requires a separately versioned validation/failure boundary; Q19 observer correction alone does not resolve this downstream gate.',limits:['Controlled readFileSync injection after imports and actual offline fixture checkpoint production; no actual device/resource exhaustion/source mutation.','No production adapter/verifier/public report/whole-output discard implemented or accepted. Fixed summary only; no raw checkpoint payload/private paths/errors published.','Shared-owner/prior exposure/authored source-dependent fixtures; no factual/heldout/model/resource/curation/routing/API acceptance.']};
fs.writeFileSync(process.argv[3],JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({passed:result.passed,failed:0}));

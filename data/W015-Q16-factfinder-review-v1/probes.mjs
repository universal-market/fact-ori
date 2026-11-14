import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const root=resolve(process.argv[2]);
const {validateCheckpointBytes:validate}=await import(pathToFileURL(join(root,'scripts/diagnostic-checkpoint-binding-v1.mjs')));
const {runOfflineCheckpoints}=await import(pathToFileURL(join(root,'scripts/diagnostic-checkpoint-worker-v1.mjs')));
const sha=b=>createHash('sha256').update(b).digest('hex');
const options={runId:'b'.repeat(32),implementationCommit:'f'.repeat(40),workerSha256:sha(readFileSync(join(root,'scripts/diagnostic-checkpoint-worker-v1.mjs')))};
const dir=mkdtempSync(join(tmpdir(),'factfinder-q16-'));let bytes;
try{await runOfflineCheckpoints({directory:dir,...options});bytes=['01-capital.json','02-unknown.json'].map(f=>readFileSync(join(dir,f)));}finally{rmSync(dir,{recursive:true,force:true});}
const checks=[];
const check=(name,fn)=>{fn();checks.push({name,result:'pass'});};
const encode=x=>Buffer.from(JSON.stringify(x));
const run=(b,o=1)=>validate(b,{...options,ordinal:o});
const reject=(b,o=1)=>assert.throws(()=>run(b,o),e=>e.message==='CHECKPOINT_BINDING_INVALID');
for(const ordinal of [1,2]){
 const raw=bytes[ordinal-1],obj=JSON.parse(raw),base=run(raw,ordinal);
 check(`case${ordinal}: reordered pretty UTF8 bytes preserve projection and bind actual digest`,()=>{
  const b=Buffer.from(JSON.stringify(Object.fromEntries(Object.entries(obj).reverse()),null,2)+'\n');const r=run(b,ordinal);
  assert.deepEqual(r.validated_projection,base.validated_projection);assert.notEqual(r.checkpoint_digest.sha256,base.checkpoint_digest.sha256);assert.equal(r.checkpoint_digest.sha256,sha(b));assert.equal(r.checkpoint_digest.observed_bytes,b.length);
 });
 check(`case${ordinal}: ignored nested proto and Unicode extensions omitted`,()=>{
  const x=JSON.parse(raw);x.result.extra=JSON.parse('{"__proto__":{"secret":"PRIVATE-雪"},"constructor":{"secret":"PRIVATE-雪"}}');const r=run(encode(x),ordinal);assert.deepEqual(r.validated_projection,base.validated_projection);assert.ok(!JSON.stringify(r).includes('PRIVATE'));assert.equal({}.secret,undefined);
 });
 check(`case${ordinal}: exact byte cap accepts whitespace padding and rejects cap+1`,()=>{
  const b=Buffer.concat([raw,Buffer.alloc(262144-raw.length,32)]);assert.equal(run(b,ordinal).checkpoint_digest.observed_bytes,262144);reject(Buffer.concat([b,Buffer.from(' ')]),ordinal);
 });
 check(`case${ordinal}: all result descendants and digest frozen; calls detached`,()=>{
  const visit=x=>{if(x&&typeof x==='object'){assert.ok(Object.isFrozen(x));Object.values(x).forEach(visit);}};visit(base);assert.throws(()=>base.checkpoint_digest.sha256='bad');assert.notEqual(base.checkpoint_digest,run(raw,ordinal).checkpoint_digest);
 });
 check(`case${ordinal}: every binding field wrong JSON type rejected`,()=>{
  for(const k of Object.keys(obj).filter(k=>k!=='result'))for(const v of [[],{},true,false,null]){const x=JSON.parse(raw);x[k]=v;reject(encode(x),ordinal);}
 });
 check(`case${ordinal}: decoded duplicate binding key rejected`,()=>{
  const t=raw.toString();reject(Buffer.from(t.replace('"run_id":','"run_\\u0069d":"'+options.runId+'","run_id":')),ordinal);
 });
 check(`case${ordinal}: fresh consent and row answer mismatches rejected`,()=>{
  for(const change of [x=>x.result.live_source_refresh=true,x=>x.result.results[0].answer='wrong']){const x=JSON.parse(raw);change(x);reject(encode(x),ordinal);}
 });
}
check('trusted fake commit correlates without Git attestation; ordinal2 alone accepted',()=>{assert.equal(run(bytes[1],2).state,'validated');});
writeFileSync(process.argv[3],JSON.stringify({schema_version:1,checks,passed:checks.length,failed:0,node:process.version,scope:'Offline single-checkpoint component only; authored source-dependent fixtures.'},null,2)+'\n');
console.log(JSON.stringify({passed:checks.length,failed:0}));

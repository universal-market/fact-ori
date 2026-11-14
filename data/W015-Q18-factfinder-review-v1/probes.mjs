import assert from 'node:assert/strict';import fs from 'node:fs';import {syncBuiltinESMExports} from 'node:module';import {join,resolve} from 'node:path';import {tmpdir} from 'node:os';import {pathToFileURL} from 'node:url';
const {observeCheckpoint:observe}=await import(pathToFileURL(join(resolve(process.argv[2]),'scripts/diagnostic-checkpoint-observation-v1.mjs')));
const d=fs.mkdtempSync(join(tmpdir(),'factfinder-q18-')),f=join(d,'01-capital.json');fs.chmodSync(d,0o700);fs.writeFileSync(f,'{"valid":"raw data"}');
const o={leaderReaped:true,directory:d,ordinal:1,readBytes:true},checks=[];
const check=(name,fn)=>{fn();checks.push({name,result:'pass'});};
const fault=(operation,code,readBytes=true)=>{const original=fs[operation];let closes=0;const originalClose=fs.closeSync;try{
 fs.closeSync=(...a)=>{closes++;return originalClose(...a);};
 fs[operation]=(...a)=>{if(operation==='closeSync'){closes++;originalClose(...a);}throw Object.assign(Error('PRIVATE'),{code});};syncBuiltinESMExports();
 const result=observe({...o,readBytes});assert.deepEqual(result,{status:'present_invalid'});assert.equal(closes,operation==='openSync'?0:1);return result;
 }finally{fs[operation]=original;fs.closeSync=originalClose;syncBuiltinESMExports();}};
try{
 for(const code of ['EMFILE','ENFILE','ENOMEM','EIO'])check(`open ${code} loses verifier/environment distinction`,()=>fault('openSync',code));
 for(const op of ['fstatSync','readSync','closeSync'])for(const code of ['EIO','EINTR'])check(`${op} ${code} returns same present_invalid`,()=>fault(op,code));
 check('metadata-only close EIO also loses distinction',()=>fault('closeSync','EIO',false));
 check('allocation failure discards bytes but loses verifier distinction',()=>{const original=Buffer.alloc;let closes=0;const close=fs.closeSync;try{Buffer.alloc=()=>{throw Object.assign(Error('PRIVATE'),{code:'ENOMEM'});};fs.closeSync=(...a)=>{closes++;return close(...a);};syncBuiltinESMExports();assert.deepEqual(observe(o),{status:'present_invalid'});assert.equal(closes,1);}finally{Buffer.alloc=original;fs.closeSync=close;syncBuiltinESMExports();}});
 check('raw buffers detached from subsequent reads and file contents',()=>{const a=observe(o);a.bytes.fill(0);assert.notDeepEqual(a.bytes,observe(o).bytes);assert.equal(fs.readFileSync(f,'utf8'),'{"valid":"raw data"}');});
 check('unreaped branch accesses only lifecycle flag',()=>{let reads=0;const options={leaderReaped:false};for(const key of ['directory','ordinal','readBytes'])Object.defineProperty(options,key,{get(){reads++;throw Error('PRIVATE');}});assert.deepEqual(observe(options),{status:'not_observed'});assert.equal(reads,0);});
 check('setup errors remain distinct fixed whole-observer failures',()=>{for(const options of [null,{}, {...o,ordinal:true},{...o,readBytes:null},{...o,directory:d+'/missing'}])assert.throws(()=>observe(options),e=>e.message==='CHECKPOINT_OBSERVATION_INVALID');});
 check('metadata mode intentionally ignores payload cap and never reads',()=>{fs.writeFileSync(f,Buffer.alloc(262145));const read=fs.readSync;let reads=0;try{fs.readSync=()=>{reads++;throw Error('PRIVATE');};syncBuiltinESMExports();assert.deepEqual(observe({...o,readBytes:false}),{status:'present_unread'});assert.deepEqual(observe(o),{status:'present_invalid'});assert.equal(reads,0);}finally{fs.readSync=read;syncBuiltinESMExports();}});
 check('unrelated files do not select checkpoint or mutate directory',()=>{fs.unlinkSync(f);fs.writeFileSync(join(d,'03-private.json'),'PRIVATE');assert.deepEqual(observe(o),{status:'absent'});assert.deepEqual(fs.readdirSync(d),['03-private.json']);});
}finally{fs.rmSync(d,{recursive:true,force:true});}
fs.writeFileSync(process.argv[3],JSON.stringify({schema_version:1,passed:checks.length,failed:0,node:process.version,checks,finding:'F1: ordinary resource/I/O/allocation failures are indistinguishable from checkpoint-invalid outcomes. Controlled builtin injection, not actual system resource exhaustion or device failure.'},null,2)+'\n');console.log(JSON.stringify({passed:checks.length,failed:0}));

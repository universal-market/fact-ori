import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,rmSync,writeFileSync} from 'node:fs';
import {resolve,join} from 'node:path';import {tmpdir} from 'node:os';import {pathToFileURL} from 'node:url';import {createHash} from 'node:crypto';
const root=resolve(process.argv[2]),sha=b=>createHash('sha256').update(b).digest('hex');
const {reconcileCheckpointPrefix:map}=await import(pathToFileURL(join(root,'scripts/diagnostic-checkpoint-prefix-v1.mjs')));
const {runOfflineCheckpoints}=await import(pathToFileURL(join(root,'scripts/diagnostic-checkpoint-worker-v1.mjs')));
const o={leaderReaped:true,runId:'d'.repeat(32),implementationCommit:'f'.repeat(40),workerSha256:sha(readFileSync(join(root,'scripts/diagnostic-checkpoint-worker-v1.mjs')))};
const d=mkdtempSync(join(tmpdir(),'factfinder-q17-'));let b;try{await runOfflineCheckpoints({directory:d,...o});b=['01-capital.json','02-unknown.json'].map(f=>readFileSync(join(d,f)));}finally{rmSync(d,{recursive:true,force:true});}
const checks=[],check=(name,fn)=>{fn();checks.push({name,result:'pass'});},abs=()=>({status:'absent'}),present=bytes=>({status:'present',bytes}),bad=Buffer.from('{'),invalid=()=>({status:'present_invalid'});
const reject=x=>assert.throws(()=>map(x,o),e=>e.message==='CHECKPOINT_PREFIX_INVALID');
const variants=[abs,invalid,()=>present(bad),()=>present(Buffer.alloc(262145)),()=>present(b[0])];
for(let i=0;i<5;i++)for(let j=0;j<5;j++)check(`state matrix first${i} second${j}`,()=>{
 const second=j===4?present(b[1]):variants[j](),r=map([variants[i](),second],o);
 assert.equal(r[0].state,i===0?'unavailable':i===4?'validated':'rejected');
 assert.equal(r[1].state,j===0?'unavailable':i===4&&j===4?'validated':'rejected');
 assert.equal(r[1].reason_code,j===0?'checkpoint_missing':i!==4?'checkpoint_order_invalid':j===4?'validated_match':'checkpoint_invalid');
 for(const row of r){assert.equal(Object.keys(row).length,5);if(row.state!=='validated')assert.equal(row.validated_projection,null);}
 if(i!==4)assert.equal(r[1].checkpoint_digest,null);
});
check('blocked bytes wrong types ignored; prefix-valid wrong types abort',()=>{for(const bytes of [null,{},'x',false,undefined]){assert.equal(map([abs(),present(bytes)],o)[1].reason_code,'checkpoint_order_invalid');reject([present(b[0]),present(bytes)]);}});
check('blocked bytes getter never accessed; descriptor extra keys still abort',()=>{let reads=0;const x={status:'present',get bytes(){reads++;throw Error('PRIVATE');}};map([invalid(),x],o);assert.equal(reads,0);reject([abs(),{...present(null),extra:true}]);});
check('unreaped observations completely ignored but options still checked',()=>{const obs=new Proxy([],{get(){throw Error('PRIVATE');}});assert.ok(map(obs,{...o,leaderReaped:false}).every(x=>x.state==='not_reconciled'));assert.throws(()=>map(obs,{...o,leaderReaped:false,runId:'bad'}),/CHECKPOINT_PREFIX_INVALID/);});
check('bounded invalid byte digest including exact cap; oversized null',()=>{for(const bytes of [Buffer.alloc(0),Buffer.from([255]),Buffer.alloc(262144)]){const r=map([present(bytes),abs()],o)[0];assert.deepEqual(r.checkpoint_digest,{kind:'full',sha256:sha(bytes),observed_bytes:bytes.length});}assert.equal(map([present(Buffer.alloc(262145)),abs()],o)[0].checkpoint_digest,null);});
check('crossordinal and semantic failures never reconstruct answers',()=>{for(const bytes of [b[1],Buffer.from(JSON.stringify({...JSON.parse(b[0]),run_id:'a'.repeat(32)}))]){const r=map([present(bytes),present(b[1])],o);assert.ok(r.every(x=>x.validated_projection===null));}});
check('all output descendants frozen, detached, no Buffer aliases or run verdict',()=>{const a=map([present(b[0]),present(b[1])],o),c=map([present(b[0]),present(b[1])],o);const visit=x=>{if(x&&typeof x==='object'){assert.ok(Object.isFrozen(x));Object.values(x).forEach(visit);}};visit(a);assert.notEqual(a[0].checkpoint_digest,c[0].checkpoint_digest);assert.equal(Object.hasOwn(a,'run_outcome'),false);assert.ok(!JSON.stringify(a).includes('PRIVATE'));});
writeFileSync(process.argv[3],JSON.stringify({schema_version:1,passed:checks.length,failed:0,node:process.version,checks,scope:'Finite trusted in-memory observations, authored offline producer; not filesystem/supervisor integration.'},null,2)+'\n');console.log(JSON.stringify({passed:checks.length,failed:0}));

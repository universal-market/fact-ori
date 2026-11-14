import test from 'node:test';import assert from 'node:assert/strict';
import {mkdtempSync,chmodSync,writeFileSync,readFileSync,readdirSync,rmSync,symlinkSync,linkSync,mkdirSync,unlinkSync} from 'node:fs';
import {tmpdir} from 'node:os';import {join} from 'node:path';
import {parseCheckpointBytes,readCheckpointJson,CHECKPOINT_BYTE_CAP as cap} from './diagnostic-checkpoint-reader-v1.mjs';
import {runOfflineCheckpoints} from './diagnostic-checkpoint-worker-v1.mjs';
import {validateCase} from './diagnostic-worker-v2.mjs';
import {createHash} from 'node:crypto';
const parse=s=>parseCheckpointBytes(Buffer.from(s));
const invalid=s=>assert.throws(()=>parse(s),/^Error: CHECKPOINT_JSON_INVALID$/);
function using(fn){const d=mkdtempSync(join(tmpdir(),'factori-q15-'));chmodSync(d,0o700);try{return fn(d);}finally{rmSync(d,{recursive:true,force:true});}}
test('valid scalars/containers/escapes follow ordinary JSON values',()=>{
 for(const x of [null,true,false,0,-1,1.25,1e20,'quote" slash\\ line\n 😀',[1,{},[]],{a:1,b:[true,null,{c:'é'}]}])assert.equal(JSON.stringify(parse(JSON.stringify(x))),JSON.stringify(x));
 assert.equal(parse(' \r\n\t1 '),1);
});
test('duplicate root keys rejected after escape decoding',()=>{invalid('{"a":1,"a":2}');invalid('{"a":1,"\\u0061":2}');});
test('nested duplicate keys rejected in objects and arrays',()=>{invalid('{"x":{"a":1,"a":2}}');invalid('[{"x":1,"x":2}]');});
test('prototype-like keys are own data without prototype mutation',()=>{
 const x=parse('{"__proto__":{"polluted":true},"constructor":1}');assert.equal(Object.getPrototypeOf(x),null);assert.equal(x.__proto__.polluted,true);assert.equal({}.polluted,undefined);
});
test('strict UTF8 rejects invalid byte sequences and BOM',()=>{
 for(const b of [Buffer.from([0xff]),Buffer.from([0xc0,0xaf]),Buffer.from([0x22,0xed,0xa0,0x80,0x22]),Buffer.from([0x22,0xf0,0x9f,0x22]),Buffer.from([0xef,0xbb,0xbf,0x31])])assert.throws(()=>parseCheckpointBytes(b),/^Error: CHECKPOINT_JSON_INVALID$/);
});
test('depth16 accepted/depth17 rejected',()=>{assert.ok(parse('['.repeat(16)+'0'+']'.repeat(16)));invalid('['.repeat(17)+'0'+']'.repeat(17));});
test('exact byte cap accepted, cap+1 rejected before parsing',()=>{
 const b=Buffer.from('"'+'x'.repeat(cap-2)+'"');assert.equal(parseCheckpointBytes(b).length,cap-2);assert.throws(()=>parseCheckpointBytes(Buffer.concat([b,Buffer.from(' ')])));
});
test('malformed delimiters/trailing data/trailing commas rejected',()=>{for(const s of ['', '{','[','[1,]','{"a":1,}','{"a" 1}','{"a":}','true false','{}x','[1 2]'])invalid(s);});
test('malformed numbers/overflow rejected; finite exponents accepted',()=>{for(const s of ['+1','01','1.','1e','--1','NaN','Infinity','1e999'])invalid(s);assert.equal(parse('-1.25e+2'),-125);});
test('invalid string controls/escapes/termination rejected',()=>{for(const s of ['"line\n"','"\\x"','"\\u12zz"','"unterminated','"\\'])invalid(s);});
test('deterministic small valid document corpus roundtrips',()=>{for(let i=0;i<100;i++){const x={id:i,label:'row '+i,values:[i%2===0,null,i/3],nested:{quote:'"\\'}};assert.equal(JSON.stringify(parse(JSON.stringify(x))),JSON.stringify(x));}});
test('fixed checkpoint reader labels parsed values unvalidated and preserves files',()=>using(d=>{
 writeFileSync(join(d,'01-capital.json'),'{"arbitrary":true}');const before=readFileSync(join(d,'01-capital.json'));const r=readCheckpointJson(d,1);assert.equal(r.status,'parsed_unvalidated');assert.equal(r.value.arbitrary,true);assert.equal(r.observed_bytes,before.length);assert.deepEqual(readFileSync(join(d,'01-capital.json')),before);
}));
test('absence only for missing fixed path',()=>using(d=>{assert.deepEqual(readCheckpointJson(d,1),{status:'absent'});assert.deepEqual(readCheckpointJson(d,2),{status:'absent'});}));
test('reader rejects oversized, malformed and duplicate-key files',()=>{for(const data of [' '.repeat(cap+1),'{bad','{"x":1,"x":2}'])using(d=>{writeFileSync(join(d,'01-capital.json'),data);assert.throws(()=>readCheckpointJson(d,1),/^Error: CHECKPOINT_READ_INVALID$/);});});
test('reader rejects symlink/hardlink/directory final paths',()=>{for(const kind of ['symlink','hardlink','directory'])using(d=>{
 const target=join(d,'target'),p=join(d,'01-capital.json');writeFileSync(target,'null');if(kind==='symlink')symlinkSync(target,p);if(kind==='hardlink')linkSync(target,p);if(kind==='directory')mkdirSync(p);assert.throws(()=>readCheckpointJson(d,1));assert.equal(readFileSync(target,'utf8'),'null');
});});
test('FIFO rejected without blocking on an unopened writer',{skip:!process.argv[2]},()=>{assert.throws(()=>readCheckpointJson(process.argv[2],1),/^Error: CHECKPOINT_READ_INVALID$/);});
test('reader rejects directory alias/bad mode/bad ordinal/relative path',()=>using(d=>{
 for(const ordinal of [0,3,true,'1'])assert.throws(()=>readCheckpointJson(d,ordinal));assert.throws(()=>readCheckpointJson('.',1));chmodSync(d,0o755);assert.throws(()=>readCheckpointJson(d,1));chmodSync(d,0o700);
 const alias=d+'-alias';symlinkSync(d,alias);try{assert.throws(()=>readCheckpointJson(alias,1));}finally{unlinkSync(alias);}assert.deepEqual(readdirSync(d),[]);
}));

test('accepted worker envelopes parse and remain explicitly unvalidated',async()=>{
 const d=mkdtempSync(join(tmpdir(),'factori-q15-worker-'));chmodSync(d,0o700);
 try{
  const workerSha256=createHash('sha256').update(readFileSync(new URL('./diagnostic-checkpoint-worker-v1.mjs',import.meta.url))).digest('hex');
  await runOfflineCheckpoints({directory:d,runId:'a'.repeat(32),implementationCommit:'b'.repeat(40),workerSha256});
  for(const ordinal of [1,2]){const r=readCheckpointJson(d,ordinal);assert.equal(r.status,'parsed_unvalidated');assert.equal(validateCase(r.value.case_id,r.value.result),true);assert.equal(r.value.ordinal,ordinal);}
 }finally{rmSync(d,{recursive:true,force:true});}
});

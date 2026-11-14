import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {runOfflineCheckpoints} from './diagnostic-checkpoint-worker-v1.mjs';
import {validateCheckpointBytes as validate} from './diagnostic-checkpoint-binding-v1.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
const options={runId:'a'.repeat(32),implementationCommit:'37a77eafa3a0f1b881780e3a012c37725078196e',workerSha256:sha(readFileSync(new URL('./diagnostic-checkpoint-worker-v1.mjs',import.meta.url)))};
const directory=mkdtempSync(join(tmpdir(),'factori-q16-'));let files;
try{await runOfflineCheckpoints({directory,...options});files=['01-capital.json','02-unknown.json'].map(name=>readFileSync(join(directory,name)));}finally{rmSync(directory,{recursive:true,force:true});}
const encode=x=>Buffer.from(JSON.stringify(x));
const changed=(ordinal,fn)=>{const x=JSON.parse(files[ordinal-1]);fn(x);return encode(x);};
const reject=(bytes,opts={...options,ordinal:1})=>assert.throws(()=>validate(bytes,opts),e=>e.message==='CHECKPOINT_BINDING_INVALID');
test('actual accepted producer cases validate with exact five-key case and nine-key projection',()=>{
 for(const ordinal of [1,2]){const r=validate(files[ordinal-1],{...options,ordinal});assert.equal(r.state,'validated');assert.equal(Object.keys(r).length,5);assert.equal(Object.keys(r.validated_projection).length,9);assert.equal(r.checkpoint_digest.sha256,sha(files[ordinal-1]));assert.equal(r.checkpoint_digest.observed_bytes,files[ordinal-1].length);assert.equal(r.validated_projection.public_review,false);}
 const capital=validate(files[0],{...options,ordinal:1});assert.equal(capital.validated_projection.answer,"Australia's national capital is Canberra.");
 const unknown=validate(files[1],{...options,ordinal:2});for(const k of ['answer','verdict','inspection','evidence_package_canonical_sha256'])assert.equal(unknown.validated_projection[k],null);
});
test('all exact envelope binding fields and types reject mutations',()=>{
 const edits={schema_version:2,run_id:'b'.repeat(32),case_id:'unknown-no-consent',ordinal:2,input_sha256:'0'.repeat(64),implementation_commit:'0'.repeat(40),worker_raw_sha256:'0'.repeat(64),import_id:'wrong'};
 for(const [k,v]of Object.entries(edits)){reject(changed(1,x=>x[k]=v));reject(changed(1,x=>x[k]=null));}
 for(const k of Object.keys(JSON.parse(files[0])))reject(changed(1,x=>delete x[k]));
 reject(changed(1,x=>x.extra='private-marker'));reject(changed(1,x=>x.ordinal=true));
});
test('trusted configuration shape and observed worker digest are checked',()=>{
 for(const [k,values]of Object.entries({runId:['A'.repeat(32),'a',null],ordinal:[0,3,true,'1',1.5],implementationCommit:['A'.repeat(40),'bad',null],workerSha256:['0'.repeat(64),'bad',null]}))for(const v of values)reject(files[0],{...options,ordinal:1,[k]:v});
 for(const opts of [undefined,null,{}])assert.throws(()=>validate(files[0],opts),e=>e.message==='CHECKPOINT_BINDING_INVALID');
});
test('actual result finite validator rejects semantic and consent changes',()=>{
 for(const edit of [x=>x.result.answer='wrong',x=>x.result.results[0].answer='wrong',x=>x.result.import_id='wrong',x=>x.result.live_source_refresh=true,x=>x.result.job={},x=>x.result.results[0].inspection.sha256='wrong'])reject(changed(1,edit));
 reject(changed(2,x=>x.result.answer='gold'));reject(changed(2,x=>x.result.results[0].evidence_package={}));
});
test('ignored result extensions are never copied into frozen public projection',()=>{
 const b=changed(1,x=>{x.result.reason='private-marker';x.result.candidates=[{secret:'private-marker'}];x.result.model_assessment={reason:'private-marker'};x.result.results[0].reason='private-marker';});
 const r=validate(b,{...options,ordinal:1});assert.ok(!JSON.stringify(r).includes('private-marker'));assert.equal(r.checkpoint_digest.sha256,sha(b));
});
test('strict parser runs before semantic use and maps errors to fixed category',()=>{
 for(const b of [Buffer.from('{"a":1,"a":2}'),Buffer.from('{'),Buffer.from([0xff]),Buffer.alloc(262145),Buffer.from('[]'),Buffer.from('null'),Buffer.from('1'),{}])reject(b);
 const text=files[0].toString();reject(Buffer.from(text.replace('"schema_version":1','"schema_version":1,"schema_version":1')));
});
test('ordinal2 validation alone makes no prefix or whole-run claim',()=>{
 const r=validate(files[1],{...options,ordinal:2});assert.equal(r.case_id,'unknown-no-consent');assert.equal(r.state,'validated');assert.ok(!Object.hasOwn(r,'run_outcome'));
 reject(files[0],{...options,ordinal:2});reject(files[1],{...options,ordinal:1});
});
test('returned projections are deeply frozen and detached between calls',()=>{
 const a=validate(files[0],{...options,ordinal:1});assert.ok(Object.isFrozen(a)&&Object.isFrozen(a.validated_projection.inspection));assert.throws(()=>a.validated_projection.inspection.claim_id='wrong');
 const b=validate(files[0],{...options,ordinal:1});assert.notEqual(a.validated_projection.inspection,b.validated_projection.inspection);assert.equal(b.validated_projection.inspection.claim_id,'C004');
});

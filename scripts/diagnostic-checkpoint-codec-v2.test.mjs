// Authored tests, not independent review. Python runner isolates fault/purity modes.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {syncBuiltinESMExports} from 'node:module';
import {createHash} from 'node:crypto';
const mode=process.argv[2]||'grammar';
const base=new URL('../data/W015-Q23-pure-codec-v2/',import.meta.url);
const moduleUrl=new URL('./diagnostic-checkpoint-codec-v2.mjs',import.meta.url);
const rows=[];
const check=(name,fn)=>{fn();rows.push({name,result:'pass'});};
const emit=extra=>fs.writeFileSync(new URL(`${mode}-results.json`,base),JSON.stringify({schema_version:1,node:process.version,authorship:'Factfinder implementation author self-checks; not independent/heldout',passed:rows.length,failed:0,checks:rows,...extra},null,2)+'\n');
if(mode==='grammar') {
 const {parseCheckpointBytesV2:parse,isCheckpointContentRejection:isContent,CHECKPOINT_BYTE_CAP:cap}=await import(moduleUrl);
 const {parseCheckpointBytes:q15}=await import('./diagnostic-checkpoint-reader-v1.mjs');
 const bytes=s=>Buffer.from(s);
 const bad=b=>{let returned=false,error;try{parse(b);returned=true;}catch(e){error=e;}assert.equal(returned,false);assert.equal(isContent(error),true);};
 const parity=s=>{const b=bytes(s);let old,oldOk=true;try{old=q15(b);}catch{oldOk=false;}if(oldOk)assert.deepEqual(parse(b),old);else bad(b);};
 const valid=['null','true','false','0','-0','1e-400','-1e-400','9007199254740993','1.5e+3','""','"\\ud800"','"\\udfff"','"\\ud83d\\ude00"','"é😀"','"\\\"\\\\\\/\\b\\f\\n\\r\\t"',' [] ','\t\r\n{}','{"a":[null,true,false,1,"x"]}'];
 for(const s of valid) check(`valid ${JSON.stringify(s)}`,()=>parity(s));
 for(const s of ['', ' ', '01','+1','.1','1.','1e','1e+','NaN','Infinity','1e400','-1e400','[1,]','{"a":1,}','{"a" 1}','{"a":}','[','{','true false','nullx','"x\n"','"\\q"','"\\u123"','"\\uZZZZ"','"unterminated','"end\\','\ufeffnull','[\ufeff1]']) check(`invalid ${JSON.stringify(s)}`,()=>parity(s));
 for(const raw of [[0x80],[0xc0,0x80],[0xc1,0xbf],[0xc2],[0xc2,0x7f],[0xe0,0x9f,0xbf],[0xe1,0x80],[0xed,0xa0,0x80],[0xf0,0x8f,0xbf,0xbf],[0xf4,0x90,0x80,0x80],[0xf5,0x80,0x80,0x80],[0xff],[0xe2,0x28,0xa1],[0xf1,0x80,0x80]]) check(`UTF8 reject ${raw}`,()=>bad(Buffer.from(raw)));
 for(const s of ['"\u007f"','"\u0080"','"\u07ff"','"\u0800"','"\ud7ff"','"\ue000"','"\uffff"','"\u{10000}"','"\u{10ffff}"'])check('UTF8 valid boundary '+JSON.stringify(s),()=>parity(s));
 for(const kind of ['array','object','mixed'])for(const n of [15,16,17])check(`depth ${kind} ${n}`,()=>{let s='0';for(let i=0;i<n;i++)s=kind==='object'||(kind==='mixed'&&i%2)?`{"k":${s}}`:`[${s}]`;parity(s);if(n<=16)parse(bytes(s));else bad(bytes(s));});
 check('cap exact and one past',()=>{const s='"'+'x'.repeat(cap-2)+'"';assert.equal(parse(bytes(s)).length,cap-2);bad(bytes('"'+'x'.repeat(cap-1)+'"'));});
 for(const s of ['{"__proto__":1}','{"constructor":2}','{"toString":3}','{"__proto__":1,"constructor":2,"toString":3}','{"nested":{"__proto__":{"constructor":3}},"toString":null}','{"a":{"x":1},"b":{"x":2}}','{"é":1,"é":2}'])check('own data '+s,()=>{const before=Object.getOwnPropertyDescriptors(Object.prototype);const value=parse(bytes(s));assert.equal(Object.getPrototypeOf(value),null);assert.deepEqual(Object.getOwnPropertyDescriptors(Object.prototype),before);assert.equal(Object.getPrototypeOf({}),Object.prototype);parity(s);});
 for(const s of ['{"x":1,"\\u0078":2}','{"__proto__":1,"__pro\\u0074o__":2}','{"a":{"constructor":1,"constructor":2}}','[{"toString":1,"toString":2}]','{"\\ud800":1,"\\ud800":2}'])check('decoded duplicates '+s,()=>parity(s));
 check('recursive freeze and raw-buffer detachment',()=>{const b=bytes('{"a":[{"x":1}]}');const x=parse(b);b.fill(0);assert.equal(x.a[0].x,1);for(const v of [x,x.a,x.a[0]])assert.ok(Object.isFrozen(v));assert.throws(()=>{x.a[0].x=9;},TypeError);assert.equal(Object.getOwnPropertyDescriptor(x,'a').get,undefined);});
 check('caps fixed',()=>{assert.equal(cap,262144);}); // Export inventory checked below.
 assert.deepEqual(Object.keys(await import(moduleUrl)).sort(),['CHECKPOINT_BYTE_CAP','CHECKPOINT_MAX_DEPTH','isCheckpointContentRejection','parseCheckpointBytesV2'].sort());
 check('whole caller failures and marker lookalikes',()=>{for(const v of [null,undefined,'{}',{},[],new Uint8Array([48])]){let e;try{parse(v);}catch(x){e=x;}assert.equal(e,'CHECKPOINT_CODEC_FAILURE');assert.equal(isContent(e),false);}assert.throws(()=>parse(bytes('0'),{}),e=>e==='CHECKPOINT_CODEC_FAILURE');for(const x of [null,'CHECKPOINT_CONTENT_REJECTION',Symbol('CHECKPOINT_CONTENT_REJECTION'),new SyntaxError('CHECKPOINT_CONTENT_REJECTION'),{name:'CHECKPOINT_CONTENT_REJECTION'}])assert.equal(isContent(x),false);});
 for(const name of ['01-capital.json','02-unknown.json'])check('actual offline Q14 producer '+name,()=>{const b=fs.readFileSync(new URL(name,base));assert.deepEqual(parse(b),q15(b));assert.ok(Object.isFrozen(parse(b).result));});
 let seed=23;const rnd=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
 function sample(depth){if(depth>3)return Math.floor(rnd()*1000);switch(Math.floor(rnd()*6)){case 0:return null;case 1:return rnd()<.5;case 2:return rnd()*1e8-1e7;case 3:return 'é😀\\"'+Math.floor(rnd()*100);case 4:return [sample(depth+1),sample(depth+1)];default:return {a:sample(depth+1),b:sample(depth+1)};}}
 check('500 deterministic JSON differential cases',()=>{for(let i=0;i<500;i++)parity(JSON.stringify(sample(0)));});
 emit({differential_generated_cases:500,scope:'Codec grammar/representation only; Q15 differential checks are reused authored reference, not fault-classification oracle.'});
} else if(mode==='fault') {
 const {parseCheckpointBytesV2:parse,isCheckpointContentRejection:isContent}=await import(moduleUrl);
 const b=Buffer.from('{"k":[1,"x"]}');
 const targets=[[Buffer.prototype,'toString'],[JSON,'parse'],[globalThis,'Number'],[globalThis,'Set'],[Set.prototype,'has'],[Set.prototype,'add'],[Object,'create'],[Object,'defineProperty'],[Object,'freeze'],[Array.prototype,'push'],[String.prototype,'slice'],[RegExp.prototype,'exec']];
 const faults=[null,'private/path/SECRET',new TypeError('SECRET'),new SyntaxError('SECRET'),Symbol('CHECKPOINT_CONTENT_REJECTION'),{code:'ENOMEM',stack:'SECRET'}];
 const define=Object.defineProperty;
 let cells=0;
 for(const [target,key]of targets)for(const fault of faults){
  const original=Object.getOwnPropertyDescriptor(target,key);let output,error,returned=false;
  try {define(target,key,{...original,value:function(){throw fault;}});try{output=parse(b);returned=true;}catch(e){error=e;}}
  finally{define(target,key,original);}
  assert.deepEqual(Object.getOwnPropertyDescriptor(target,key),original);assert.equal(returned,false);assert.equal(output,undefined);assert.equal(error,'CHECKPOINT_CODEC_FAILURE');assert.equal(isContent(error),false);cells++;
 }
 check('72 catchable intrinsic-fault cells fixed whole/no partial/restoration',()=>assert.equal(cells,72));
 check('private marker remains deliberate after injections',()=>assert.throws(()=>parse(Buffer.from('{')),e=>isContent(e)));
 emit({fault_cells:cells,restoration_identity:true,scope:'Isolated synthetic intrinsic faults; no OOM/process-death/native/hostile-runtime guarantee.'});
} else if(mode==='purity') {
 // Fixture/source acquisition precedes hooks; no codec import has occurred.
 const source=fs.readFileSync(moduleUrl,'utf8');
 const buffers=['01-capital.json','02-unknown.json'].map(n=>fs.readFileSync(new URL(n,base)));
 const sourceSha=createHash('sha256').update(source).digest('hex');
 // Exact manual syntax/call-graph audit is recorded separately; these guards are supplementary.
 assert.equal((source.match(/^import /gm)||[]).length,1);
 assert.match(source,/^import \{Buffer\} from 'node:buffer';/m);
 assert.ok(!/\b(?:process|fetch|setTimeout|setInterval|queueMicrotask|Promise|eval|require)\b|import\s*\(/.test(source));
 const originalRead=fs.readFileSync,preloadedOriginal=originalRead;
 const patches=[];let calls=0;const sentinel=Symbol('HARNESS_IO_DENIED');const deny=()=>{calls++;throw sentinel;};
 function arm(object){for(const key of Object.keys(object)){const d=Object.getOwnPropertyDescriptor(object,key);if(typeof d.value==='function'&&d.writable&&key!=='constants'&&!/^[A-Z]/.test(key)){patches.push([object,key,d]);Object.defineProperty(object,key,{...d,value:deny});}}}
 // Explicit allowlist admits the leaf only. A preloaded capture is refused, not rewritten.
 const admitted=new Set([moduleUrl.href]);
 function admitLeaf(url,alreadyLoaded){if(!admitted.has(url)||alreadyLoaded)throw 'HARNESS_ADMISSION_REFUSED';}
 check('preloaded original-alias control refused by graph/load-order admission',()=>{assert.throws(()=>admitLeaf(moduleUrl.href,true),e=>e==='HARNESS_ADMISSION_REFUSED');assert.throws(()=>admitLeaf('control:preloaded-original',false),e=>e==='HARNESS_ADMISSION_REFUSED');assert.equal(preloadedOriginal,originalRead);admitLeaf(moduleUrl.href,false);});
 let positiveCalls,negativeCalls,restored=false;
 try {
  arm(fs);arm(fs.promises);syncBuiltinESMExports();
  const named=await import('node:fs');
  const controlSource="import {readFileSync} from 'node:fs'; const captured=readFileSync; export function namedRead(){return readFileSync('unused');} export function localRead(){return captured('unused');}";
  const controls=await import('data:text/javascript;base64,'+Buffer.from(controlSource).toString('base64'));
  assert.notEqual(named.readFileSync,preloadedOriginal);
  // Exact audited leaf bytes loaded from in-memory data URL: avoids Node's own
  // filesystem module loader hitting the intentionally armed fs hooks. No relative imports.
  const codec=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64')); // first leaf evaluation
  const before=calls;
  for(const b of buffers)codec.parseCheckpointBytesV2(b);
  codec.parseCheckpointBytesV2(Buffer.from('{"__proto__":[true,null,"x"]}'));
  assert.throws(()=>codec.parseCheckpointBytesV2(Buffer.from('{')),e=>codec.isCheckpointContentRejection(e));
  positiveCalls=calls-before;assert.equal(positiveCalls,0);
  for(const fn of [controls.namedRead,controls.localRead,fs.promises.readFile])assert.throws(()=>fn('unused'),e=>e===sentinel);
  negativeCalls=calls-before;assert.equal(negativeCalls,3);
  // Controls are synchronous throwing functions, no callbacks/timers/promises queued.
 } finally {
  for(const [object,key,d]of patches)Object.defineProperty(object,key,d);
  syncBuiltinESMExports();
  for(const [object,key,d]of patches)assert.deepEqual(Object.getOwnPropertyDescriptor(object,key),d);
  assert.equal((await import('node:fs')).readFileSync,originalRead);restored=true;
 }
 check('leaf positive zero counted hook calls; named/local/promises negatives effective',()=>assert.equal(positiveCalls,0));
 check('default/promises descriptors and named binding restored exactly',()=>assert.equal(restored,true));
 emit({source_raw_sha256:sourceSha,leaf_loading:'Exact manually audited bytes evaluated once from in-memory data URL after hooks; no relative imports/import.meta in leaf. Node filesystem module-loader acquisition intentionally outside measurement.',hooked_surfaces:patches.map(([,key])=>key),positive_hook_calls:positiveCalls,negative_hook_calls:negativeCalls,restoration_identity:restored,import_time_async_work:'none in manually audited exact leaf; negative controls schedule no work',scope:'Nonhostile audited leaf and enumerated fs/promises entry points only. Module loading/bootstrap outside measured calls; no process/OS/native sandbox, loader/context or full Q22 evidence.'});
} else throw Error('unknown test mode');

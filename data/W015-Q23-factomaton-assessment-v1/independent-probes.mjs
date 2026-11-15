// Factomaton non-author checks. Finite/source-dependent, not held out or factual review.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const root=resolve(process.argv[2]),output=process.argv[3];
const codec=await import(pathToFileURL(resolve(root,'scripts/diagnostic-checkpoint-codec-v2.mjs')));
const parse=codec.parseCheckpointBytesV2,content=codec.isCheckpointContentRejection;
const rows=[];const check=(name,fn)=>{fn();rows.push({name,result:'pass'});};
const decode=s=>parse(Buffer.from(s));
const invalid=b=>{let returned=false,e;try{parse(b);returned=true;}catch(x){e=x;}assert.equal(returned,false);assert.equal(content(e),true);};
const whole=fn=>{let returned=false,e;try{fn();returned=true;}catch(x){e=x;}assert.equal(returned,false);assert.equal(e,'CHECKPOINT_CODEC_FAILURE');assert.equal(content(e),false);};
function inspect(value){if(value&&typeof value==='object'){assert.ok(Object.isFrozen(value));if(!Array.isArray(value))assert.equal(Object.getPrototypeOf(value),null);for(const d of Object.values(Object.getOwnPropertyDescriptors(value)))assert.equal(d.get,undefined);for(const x of Object.values(value))inspect(x);}}
check('all JSON root kinds remain unvalidated and deeply frozen',()=>{for(const s of ['null','true','false','42','"x"','[]','{}','{"z":[{"a":1}]}']){const x=decode(s);assert.equal(JSON.stringify(x),JSON.stringify(JSON.parse(s)));inspect(x);}});
check('numeric edge values compared directly to native JSON semantics',()=>{for(const s of ['-0','-1e-999','1e-999','9007199254740993','1.7976931348623157e308','2.2250738585072014e-308'])assert.ok(Object.is(decode(s),JSON.parse(s)));for(const s of ['1e309','-1e999'])invalid(Buffer.from(s));});
check('byte cap inclusive with whitespace and multibyte payloads',()=>{const n=codec.CHECKPOINT_BYTE_CAP;assert.equal(parse(Buffer.concat([Buffer.from('0'),Buffer.alloc(n-1,32)])),0);invalid(Buffer.concat([Buffer.from('0'),Buffer.alloc(n,32)]));const s='"'+'é'.repeat((n-2)/2)+'"';assert.equal(Buffer.byteLength(s),n);assert.equal(decode(s).length,(n-2)/2);});
check('mixed object-array container depth exactly16 versus17',()=>{for(const n of [16,17]){let s='0';for(let i=0;i<n;i++)s=i%2?'[ '+s+' ]':'{"k":'+s+'}';if(n===16)inspect(decode(s));else invalid(Buffer.from(s));}});
check('own special names and composition-distinct Unicode keys do not pollute',()=>{const prior=Object.getOwnPropertyDescriptors(Object.prototype);const x=decode('{"__proto__":{"polluted":1},"constructor":0,"toString":[],"é":1,"é":2}');assert.equal(Object.hasOwn(x,'__proto__'),true);assert.equal(x['é'],1);assert.equal(x['é'],2);assert.equal({}.polluted,undefined);assert.deepEqual(Object.getOwnPropertyDescriptors(Object.prototype),prior);inspect(x);});
check('decoded escapes and surrogate pairs duplicate exact strings only',()=>{for(const s of ['{"a":0,"\\u0061":1}','{"😀":0,"\\ud83d\\ude00":1}','{"\\ud800":0,"\\ud800":1}','[{"x":0,"x":1}]'])invalid(Buffer.from(s));const x=decode('{"a":{"x":0},"b":{"x":1},"\\ud800":1,"\\ud801":2}');assert.equal(x.a.x,0);assert.equal(x.b.x,1);});
check('BOM rejected outside strings but retained as quoted JSON data',()=>{for(const s of ['\ufeff0',' [\ufeff0]','0\ufeff'])invalid(Buffer.from(s));assert.equal(decode('"\ufeff"'),'\ufeff');assert.equal(decode('"\\ufeff"'),'\ufeff');});
check('raw UTF8 boundary encodings and isolated continuations',()=>{for(const p of [0x80,0xc0,0xc1,0xf5,0xff])invalid(Buffer.from([34,p,34]));for(const a of [[0xe0,0x80,0x80],[0xed,0xbf,0xbf],[0xf4,0x90,0x80,0x80],[0xf0,0x90,0x80]])invalid(Buffer.from([34,...a,34]));for(const x of ['\u0080','\u07ff','\u0800','\ud7ff','\ue000','\u{10ffff}'])assert.equal(decode(JSON.stringify(x)),x);});
check('all unescaped ASCII control characters rejected inside strings',()=>{for(let i=0;i<32;i++)invalid(Buffer.from([34,i,34]));});
check('escaped lone surrogates preserved while raw surrogate UTF8 rejects',()=>{assert.equal(decode('"\\ud800"').charCodeAt(0),0xd800);assert.equal(decode('"\\udfff"').charCodeAt(0),0xdfff);invalid(Buffer.from([34,0xed,0xa0,0x80,34]));});
check('prefix/suffix JSON token concatenations never return partial value',()=>{for(const s of ['nullnull','true0','00','[0]false','{}{}','"a""b"','1e','1.','-','[true false]','{"x":0}x'])invalid(Buffer.from(s));});
check('ordinary Buffer data detached from recursive decoded tree',()=>{const b=Buffer.from('{"x":["stay",{"n":7}]}');const v=parse(b);b.fill(0);assert.equal(v.x[0],'stay');assert.equal(v.x[1].n,7);inspect(v);});
check('caller contract failures distinct from malformed raw bytes',()=>{whole(()=>parse());whole(()=>parse(new Uint8Array([48])));whole(()=>parse(Buffer.from('0'),undefined));invalid(Buffer.from('{'));});
check('unexpected proven-string conversion exception becomes fixed whole failure',()=>{const saved=JSON.parse;try{JSON.parse=()=>{throw null;};whole(()=>decode('"valid"'));}finally{JSON.parse=saved;}assert.equal(JSON.parse,saved);assert.equal(decode('"ok"'),'ok');});
check('same-description marker and arbitrary classes are never content',()=>{for(const x of [Symbol('CHECKPOINT_CONTENT_REJECTION'),'CHECKPOINT_CONTENT_REJECTION',{},new TypeError('CHECKPOINT_CONTENT_REJECTION')])assert.equal(content(x),false);});
let seed=83281;const rnd=()=>{seed=(Math.imul(seed,1103515245)+12345)>>>0;return seed;};
function sample(depth){if(depth>4)return (rnd()%10000)/7;switch(rnd()%7){case 0:return null;case 1:return !!(rnd()%2);case 2:return (rnd()%1000000)-500000;case 3:return ['é','é','\ud800','\ufeff','"\\\n',String.fromCodePoint(0x10000+rnd()%0x10000)][rnd()%6];case 4:return [sample(depth+1),sample(depth+1)];case 5:return {['k'+(rnd()%100)]:sample(depth+1)};default:return {left:sample(depth+1),right:sample(depth+1)};}}
check('800 separately seeded generated JSON values match native roundtrip',()=>{for(let i=0;i<800;i++){const s=JSON.stringify(sample(0));const x=decode(s);assert.equal(JSON.stringify(x),s);inspect(x);}});
check('both published producer fixtures parse without semantic endorsement',()=>{for(const n of ['01-capital.json','02-unknown.json']){const b=fs.readFileSync(resolve(root,'data/W015-Q23-pure-codec-v2',n));const x=parse(b);assert.equal(JSON.stringify(x),JSON.stringify(JSON.parse(b.toString('utf8'))));inspect(x);}});
fs.writeFileSync(output,JSON.stringify({schema_version:1,task_key:'FO-W015-Q23',reviewer:'@adrian.factomaton',node:process.version,passed:rows.length,failed:0,generated_cases:800,checks:rows,scope:'Non-author finite codec checks; shared owner/source dependence/prior exposure, not held-out/semantic/factual/full-pipeline acceptance.'},null,2)+'\n');
console.log(JSON.stringify({passed:rows.length,generated_cases:800}));

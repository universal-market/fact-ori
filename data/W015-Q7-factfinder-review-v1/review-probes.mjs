import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,copyFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {DatabaseSync} from 'node:sqlite';
const root=resolve(process.argv[2]),scratch=resolve(process.argv[3]);mkdirSync(scratch,{recursive:true});
const {FactEngine,engineFingerprint,digest}=await import(pathToFileURL(root+'/service/engine.mjs'));
const read=p=>JSON.parse(readFileSync(root+'/'+p));const lib=read('public/library.json'),off=read('scripts/fixtures/c007a-v3/pending-consumer-results-v1.json');const checks=[];const clone=x=>JSON.parse(JSON.stringify(x));
const check=(label,value)=>{assert(value,label);checks.push(label);};
const invalid=e=>e.code==='INVALID_PUBLIC_SNAPSHOT'&&e.message==='Unsupported or malformed public evidence snapshot';
const mutations=[];
for(let i=0;i<8;i++)for(const [field,value]of [['state','pending'],['selected_version',true],['claim_id','missing'],['answer','injected']]){const s=clone(lib);s.records[i].evidence_package[field]=value;mutations.push([`row${i}/${field}`,s]);}
for(let i=0;i<lib.exact_mappings.length;i++){const s=clone(lib);s.exact_mappings.push(clone(s.exact_mappings[i]));mutations.push([`mapping${i}/duplicate`,s]);}
mutations.push(['offline-seed',off.seed],['offline-export',off.export],['forged-export',{...off.export,schema_version:1,kind:lib.kind}],['schema',{...lib,schema_version:2}]);
for(const[label,snapshot]of mutations){let sql=0,model=0;assert.throws(()=>new FactEngine({snapshot,db:{exec(){sql++;}},model:{embed(){model++;}}}),invalid);check('constructor/'+label,sql===0&&model===0);}
const db=new DatabaseSync(':memory:');let embeddings=0;const model={embeddingRevision:'review-stub-v1',embeddingModel:'stub',embed:async texts=>{embeddings+=texts.length;return texts.map(()=>[1,2,3]);}};const engine=new FactEngine({snapshot:clone(lib),db,model,backend:'http://unused.invalid'});
try{
 for(const[label,snapshot]of mutations){engine.snapshot=snapshot;await assert.rejects(engine.initialize(),invalid);check('initialize/'+label,embeddings===0&&engine.records.length===0&&db.prepare('SELECT count(*) AS n FROM vectors').get().n===0);}
 engine.snapshot=clone(lib);await engine.initialize();check('cold-eight',engine.records.length===8&&embeddings===8);const cache=db.prepare('SELECT * FROM vectors ORDER BY key').all();await engine.initialize();check('warm-eight',embeddings===8&&JSON.stringify(cache)===JSON.stringify(db.prepare('SELECT * FROM vectors ORDER BY key').all()));
 for(const[label,snapshot]of mutations){engine.snapshot=snapshot;await assert.rejects(engine.initialize(),invalid);check('reinitialize/'+label,engine.records.length===0&&embeddings===8&&JSON.stringify(cache)===JSON.stringify(db.prepare('SELECT * FROM vectors ORDER BY key').all()));}
 engine.snapshot={...clone(lib),records:[],exact_mappings:[]};await engine.initialize();check('empty-retains-unadmitted-cache',engine.records.length===0&&embeddings===8&&db.prepare('SELECT count(*) AS n FROM vectors').get().n===8);
}finally{db.close();}
const names=['engine.mjs','server.mjs','models.json','snapshot-boundary.mjs'];check('exact-fingerprint-input-order',engineFingerprint()===digest(names.map(n=>readFileSync(root+'/service/'+n,'utf8')).join('\n')));
const copied=scratch+'/fingerprint';mkdirSync(copied,{recursive:true});for(const n of names)copyFileSync(root+'/service/'+n,copied+'/'+n);const before=(await import(pathToFileURL(copied+'/engine.mjs'))).engineFingerprint();check('copied-fingerprint-equal',before===engineFingerprint());writeFileSync(copied+'/snapshot-boundary.mjs',readFileSync(copied+'/snapshot-boundary.mjs','utf8')+'\n// reviewer fingerprint mutation\n');check('guard-byte-change-invalidates-fingerprint',(await import(pathToFileURL(copied+'/engine.mjs'))).engineFingerprint()!==before);
// Prepare public invalid fixtures for direct-shell startup tests (no child spawning from Node).
writeFileSync(scratch+'/offline-seed.json',JSON.stringify(off.seed));writeFileSync(scratch+'/offline-export.json',JSON.stringify(off.export));writeFileSync(scratch+'/malformed.json','{"UNTRUSTED_REVIEW_PAYLOAD_MARKER":');
console.log(JSON.stringify({schema_version:1,task:'FO-W015-Q7',passed:checks.length,failed:0,checks,limits:'Finite serialized fixtures, in-memory SQLite and deterministic embedding stubs. No production model/backend, concurrency or resource proof.'},null,2));

// Finite reviewer-written serialized-boundary probes; not authenticity or full audit validation.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const root=resolve(process.argv[2]);
const {assertPublicSnapshot:validate}=await import(pathToFileURL(root+'/service/snapshot-boundary.mjs'));
const read=p=>JSON.parse(readFileSync(root+'/'+p));
const library=read('public/library.json'),offline=read('scripts/fixtures/c007a-v3/pending-consumer-results-v1.json');
const checks=[];const clone=x=>JSON.parse(JSON.stringify(x));
function good(label,x){const before=JSON.stringify(x);assert.equal(validate(x),undefined,label);assert.equal(JSON.stringify(x),before,label);checks.push(label);}
function bad(label,x){const before=JSON.stringify(x);assert.throws(()=>validate(x),e=>e.code==='INVALID_PUBLIC_SNAPSHOT'&&e.message==='Unsupported or malformed public evidence snapshot',label);assert.equal(JSON.stringify(x),before,label);checks.push(label);}
function change(label,path,value){const x=clone(library);let p=x;for(const k of path.slice(0,-1))p=p[k];p[path.at(-1)]=value;bad(label,x);}
good('actual-public-export',library);
for(const [name,fixture] of [['seed',offline.seed],['export',offline.export]]){
 bad('offline/'+name,fixture);bad('forged-envelope/'+name,{...fixture,schema_version:1,kind:library.kind});
}
for(const k of Object.keys(library)){const x=clone(library);delete x[k];bad('missing-envelope/'+k,x);}
for(const k of ['library_import_id','snapshot_sha256','curation_log_sha256'])for(const [i,v] of [null,true,[],{},'a'.repeat(63),'A'.repeat(64),'a'.repeat(65),'g'.repeat(64)].entries())change(`hash/${k}/${i}`,[k],v);
for(const [k,values] of Object.entries({schema_version:[true,'1',0,2],kind:[null,'offline_withheld_export_diagnostic',''],records:[null,{},true],withheld:[null,{},true],exact_mappings:[null,{},true],limits:[null,{},[null],['']],curation_as_of:[false,1,[]],implementation_review:[null,false,' ']}))for(const [i,v]of values.entries())change(`envelope/${k}/${i}`,[k],v);
change('extra-envelope',['untrusted_payload'],'sensitive-marker');
for(let i=0;i<library.records.length;i++){
 const row=library.records[i];
 for(const field of ['claim_id','sha256','version','record','evidence_package','source_reviews']){const x=clone(library);delete x.records[i][field];bad(`record/${i}/missing/${field}`,x);}
 for(const v of [true,0,-1,1.5,Number.MAX_SAFE_INTEGER+1,'1',null])change(`record/${i}/version/${JSON.stringify(v)}`,['records',i,'version'],v);
 for(const [path,v]of [[['record','id'],'wrong'],[['record','version'],row.version+1],[['record','claim'],' '],[['record','answer'],null],[['record','scope'],[]],[['evidence_package','claim_id'],'wrong'],[['evidence_package','selected_version'],row.version+1],[['evidence_package','state'],'pending'],[['evidence_package','answer'],'injected'],[['evidence_package','answer_kind'],'contradicted'],[['source_reviews'],{}]])change(`record/${i}/${path.join('/')}`,['records',i,...path],v);
 const dup=clone(library);dup.records.push(clone(row));bad(`record/${i}/duplicate`,dup);
}
for(let i=0;i<library.exact_mappings.length;i++){
 const m=library.exact_mappings[i];const x=clone(library);x.exact_mappings.push(clone(m));bad(`mapping/${i}/duplicate`,x);
 for(const v of ['',null,1,[]])change(`mapping/${i}/question/${JSON.stringify(v)}`,['exact_mappings',i,'question'],v);
 change(`mapping/${i}/kind`,['exact_mappings',i,'kind'],'outside_scope');
 change(`mapping/${i}/extra`,['exact_mappings',i,'extra'],'sensitive-marker');
 if(m.kind==='claim')for(const [k,v]of [['claim_id','missing'],['version',true],['version',m.version+1],['sha256','0'.repeat(64)]])change(`mapping/${i}/pin/${k}/${v}`,['exact_mappings',i,k],v);
 else{change(`mapping/${i}/clarification`,['exact_mappings',i,'clarification'],' ');change(`mapping/${i}/target`,['exact_mappings',i,'claim_id'],library.records[0].claim_id);}
}
const empty={...clone(library),records:[],exact_mappings:[],withheld:[]};good('empty-approved',empty);
for(const state of ['pending','reopened','retired','unselected'])for(const v of [null,1])good(`withheld/${state}/${v}`,{...empty,withheld:[{claim_id:'offline',state,selected_version:v}]});
for(const row of [{claim_id:'x',state:'approved',selected_version:1},{claim_id:'x',state:'pending',selected_version:true},{claim_id:' ',state:'pending',selected_version:1}])bad('withheld/invalid/'+JSON.stringify(row),{...empty,withheld:[row]});
bad('withheld/duplicate',{...empty,withheld:[{claim_id:'x',state:'pending',selected_version:1},{claim_id:'x',state:'retired',selected_version:1}]});
bad('withheld/approved-collision',{...clone(library),withheld:[{claim_id:library.records[0].claim_id,state:'pending',selected_version:1}]});
const literal=clone(library),m=literal.exact_mappings.find(x=>x.kind==='claim');for(const question of [m.question.toUpperCase(),' '+m.question,m.question+' ',m.question+'\u200b'])literal.exact_mappings.push({...m,question});good('distinct-literal-keys',literal);
// Expected scope limits: structurally coherent invented approvals and nested audit extras pass.
const coherent=clone(library);coherent.snapshot_sha256='0'.repeat(64);coherent.records[0].record.answer='invented';coherent.records[0].evidence_package.answer='invented';good('limit/coherent-invention-not-authenticated',coherent);
const audit=clone(library);audit.records[0].evidence_package.unchecked_audit={future:true};good('limit/not-full-audit-schema',audit);
const src=readFileSync(root+'/service/snapshot-boundary.mjs','utf8');assert(!/^import\s/m.test(src));assert(!/snapshot-boundary/.test(readFileSync(root+'/service/engine.mjs','utf8')));assert(!/snapshot-boundary/.test(readFileSync(root+'/service/server.mjs','utf8')));checks.push('standalone-no-imports-or-engine-server-wiring');
console.log(JSON.stringify({schema_version:1,task:'FO-W015-Q6',passed:checks.length,failed:0,checks,limits:'Finite serialized fixtures only. No authentication/content hash/factual/full audit schema proof, generic JS object/security/resource guarantee or runtime integration.'},null,2));

// Independent finite correction matrix; source root argv[2], no live endpoints.
import {pathToFileURL} from 'node:url';import path from 'node:path';import assert from 'node:assert/strict';
const root=path.resolve(process.argv[2]);const v2=await import(pathToFileURL(path.join(root,'scripts/diagnostic-worker-v2.mjs')));const v1=await import(pathToFileURL(path.join(root,'scripts/diagnostic-worker.mjs')));
const a=await v2.runOffline(),b=await v1.runOffline();assert.deepEqual(a.results,b.results);
const observations=[];function check(name,index,fn,want){const r=structuredClone(a.results[index].result);fn(r);let got;try{got=v2.validateCase(a.results[index].case_id,r)===true;}catch{got=false;}assert.equal(got,want,name);observations.push({name,accepted:got});}
for(const level of ['top','row']){const target=r=>level==='top'?r:r.results[0];
 for(const key of ['evidence','evidence_package','inspection','query_evidence_relation','query_relationship_review'])for(const value of [null,{},'supports_answer'])check('unknown '+level+' '+key+' '+JSON.stringify(value),1,r=>{target(r)[key]=value;},false);
 check('unknown '+level+' inherited full capital evidence',1,r=>{target(r).evidence=structuredClone(b.results[0].result.evidence);},false);
 check('unknown '+level+' absent serialized undefined fields',1,r=>{for(const k of ['evidence','evidence_package','inspection','query_evidence_relation','query_relationship_review'])target(r)[k]=undefined;},true);
 for(const key of ['record_supporting','record_challenging','context']){
  check('capital '+level+' extra '+key,0,r=>{target(r).evidence[key].push({relation:'supports',quote:'unbound'});},false);
  check('capital '+level+' missing '+key,0,r=>{delete target(r).evidence[key];},false);
 }
 check('capital '+level+' extra evidence partition field',0,r=>{target(r).evidence.unbound=[];},false);
 check('capital '+level+' changed evidence relation',0,r=>{target(r).query_evidence_relation='challenges_input';},false);
 check('capital '+level+' exact duplicate JSON roundtrip',0,r=>{},true);
 for(const index of [0,1])check('case '+index+' '+level+' refresh true',index,r=>{target(r).live_source_refresh=true;},false);
}
check('unknown row refresh false is not omitted',1,r=>{r.results[0].live_source_refresh=false;},false);
check('unknown row refresh null is not omitted',1,r=>{r.results[0].live_source_refresh=null;},false);
check('capital swaps support/context partitions',0,r=>{[r.evidence.record_supporting,r.evidence.context]=[r.evidence.context,r.evidence.record_supporting];},false);
console.log(JSON.stringify({schema_version:1,task_key:'FO-W015-Q11',node:process.version,same_frozen_case_results_as_v1:true,checks:observations.length,passed:observations.length,observations},null,2));

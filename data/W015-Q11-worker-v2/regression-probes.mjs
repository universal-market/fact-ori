// Reviewer probes for Q11 successor of exact Q10 probes; pass source root as argv[2]. Offline only.
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const {runOffline,validateCase,loadInputs,fixtureBackend}=await import(pathToFileURL(path.resolve(process.argv[2],'scripts/diagnostic-worker-v2.mjs')));
const report=await runOffline();const observations=[];
function probe(name,index,mutate,expected){const r=structuredClone(report.results[index].result);mutate(r);let accepted;try{accepted=validateCase(report.results[index].case_id,r)===true;}catch{accepted=false;}observations.push({name,expected,observed:accepted?'accepted':'rejected',meets_expectation:(accepted?'accepted':'rejected')===expected});}
probe('unknown top-level inherited evidence',1,r=>{r.evidence=structuredClone(report.results[0].result.evidence);},'rejected');
probe('unknown row inherited evidence',1,r=>{r.results[0].evidence=structuredClone(report.results[0].result.evidence);},'rejected');
probe('unknown top-level asserts supported evidence relation',1,r=>{r.query_evidence_relation='supports_answer';},'rejected');
probe('unknown row claims live source refresh',1,r=>{r.results[0].live_source_refresh=true;},'rejected');
probe('capital row inherited evidence altered',0,r=>{r.results[0].evidence={record_supporting:[{quote:'fabricated'}]};},'rejected');
probe('unknown nested evidence package rejected',1,r=>{r.results[0].evidence_package={answer:'Au'};},'rejected');
probe('unknown nested inspection rejected',1,r=>{r.results[0].inspection={claim_id:'C004'};},'rejected');
probe('top level nonnull job rejected',1,r=>{r.job={id:'x'};},'rejected');
probe('row submission rejected',1,r=>{r.results[0].research_submission='queued';},'rejected');
probe('capital top inspection extra field rejected',0,r=>{r.inspection.extra=true;},'rejected');
probe('capital row full package mutation rejected',0,r=>{r.results[0].evidence_package.answer='Au';},'rejected');
probe('unknown top refresh rejected',1,r=>{r.live_source_refresh=true;},'rejected');
probe('row model revision rejected',1,r=>{r.results[0].model_revision='0'.repeat(64);},'rejected');
probe('wrong verbatim claim rejected',1,r=>{r.results[0].claim='Au';},'rejected');
const {snapshot}=loadInputs();const counts={backend_checks:0,forbidden_submissions:0,record_revalidations:0};const backend=fixtureBackend(snapshot,counts);
for(const route of ['/unknown','/v1/records/C004?version=2&sha256='+snapshot.records.find(r=>r.claim_id==='C004').sha256]){let rejected=false;try{await backend(route);}catch{rejected=true;}assert(rejected);observations.push({name:'backend rejects '+route,expected:'rejected',observed:'rejected',meets_expectation:true});}
console.log(JSON.stringify({schema_version:1,task_key:'FO-W015-Q11',node:process.version,offline:true,observations,expected_rejections:observations.length,unexpected_acceptances:observations.filter(x=>!x.meets_expectation).length},null,2));

import test from 'node:test';
import assert from 'node:assert/strict';
import {runOffline,validateCase,loadInputs,fixtureBackend} from './diagnostic-worker-v2.mjs';
const events=[],report=await runOffline(e=>events.push(e));
test('actual engine passes exact two frozen fixture cases and ordered events',()=>{
 assert.deepEqual(events.map(x=>x.phase),['startup','capital-paraphrase','unknown-no-consent']);
 assert.equal(report.counts.document_embeddings,8);assert.equal(report.counts.query_embeddings,2);
 assert.equal(report.counts.record_revalidations,1);assert.equal(report.counts.forbidden_submissions,0);
 for(const row of report.results)assert.equal(validateCase(row.case_id,row.result),true);
});
const mutations={
 'wrong input':r=>{r.text='changed';},'wrong import':r=>{r.import_id='bad';},
 'wrong top label':r=>{r.status='contradicted';},'wrong row label':r=>{r.results[0].status='contradicted';},
 'answer mismatch':r=>{r.answer='Sydney';},'wrong verdict':r=>{r.results[0].verdict='contradicted';},
 'unexpected job':r=>{r.results[0].job={id:'not-consented'};},
 'submission marker':r=>{r.research_submission='queued';},
 'wrong model revision':r=>{r.model_revision='bad';},
 'wrong source span':r=>{r.results[0].end--;},
 'extra claim':r=>{r.results.push(structuredClone(r.results[0]));},
 'wrong record pin':r=>{r.results[0].inspection.sha256='0'.repeat(64);},
 'changed package':r=>{r.evidence_package.answer='changed';},
 'unreviewed relation':r=>{r.query_relationship_review='approved';},
};
for(const [name,mutate]of Object.entries(mutations))test('reject '+name,()=>{
 const r=structuredClone(report.results[0].result);mutate(r);assert.throws(()=>validateCase('capital-paraphrase',r),/DIAGNOSTIC_MISMATCH/);
});
test('unknown cannot inherit evidence package or answer',()=>{
 for(const mutate of [r=>{r.evidence_package={answer:'Au'};},r=>{r.answer='Au';},r=>{r.inspection={claim_id:'C012'};}]){
  const r=structuredClone(report.results[1].result);mutate(r);assert.throws(()=>validateCase('unknown-no-consent',r));
 }
});
test('unknown case ID rejected',()=>assert.throws(()=>validateCase('other',report.results[0].result)));
test('backend fixture rejects consenttrue and incorrect record pins',async()=>{
 const {snapshot}=loadInputs(),counts={backend_checks:0,forbidden_submissions:0,record_revalidations:0};const backend=fixtureBackend(snapshot,counts);
 await assert.rejects(backend('/v1/check',{body:JSON.stringify({text:'Gold',public_review:true})}));
 await assert.rejects(backend('/v1/records/C004?version=1&sha256='+'0'.repeat(64)));
 assert.equal(counts.forbidden_submissions,1);assert.equal(counts.record_revalidations,0);
});

// Required evidence and provenance regression matrix, both levels.
for(const index of [0,1])for(const level of ['top','row']){
 const prefix=(index===0?'capital':'unknown')+' '+level;
 const mutate=fn=>{const r=structuredClone(report.results[index].result);fn(level==='top'?r:r.results[0]);
  assert.throws(()=>validateCase(report.results[index].case_id,r),/DIAGNOSTIC_MISMATCH/);};
 test(prefix+' rejects inherited/fabricated evidence',()=>mutate(x=>{x.evidence=index===1?structuredClone(report.results[0].result.evidence):{record_supporting:[{quote:'fabricated'}]};}));
 test(prefix+' rejects contradictory evidence relation',()=>mutate(x=>{x.query_evidence_relation=index===1?'supports_answer':'challenges_input';}));
 test(prefix+' rejects live refresh claim',()=>mutate(x=>{x.live_source_refresh=true;}));
 if(index===0){
  test(prefix+' rejects omitted evidence',()=>mutate(x=>{delete x.evidence;}));
  test(prefix+' rejects changed challenging evidence',()=>mutate(x=>{x.evidence.record_challenging.push({quote:'fabricated'});}));
  test(prefix+' rejects changed context evidence',()=>mutate(x=>{x.evidence.context.push({quote:'fabricated'});}));
 }else{
  for(const key of ['evidence','query_evidence_relation','query_relationship_review','evidence_package','inspection'])
   test(prefix+' rejects explicit null '+key,()=>mutate(x=>{x[key]=null;}));
 }
}

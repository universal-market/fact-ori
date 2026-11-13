import test from 'node:test';
import assert from 'node:assert/strict';
import {runOffline,validateCase,loadInputs,fixtureBackend} from './diagnostic-worker.mjs';
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

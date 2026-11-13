// OFFLINE fixture worker only. No live model/backend endpoint or environment switch.
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {fileURLToPath} from 'node:url';
import {FactEngine, engineFingerprint} from '../service/engine.mjs';
const root=new URL('../',import.meta.url);
const sha=b=>createHash('sha256').update(b).digest('hex');
export const compact=value=>Array.isArray(value)?'['+value.map(compact).join(',')+']':
  value!==null&&typeof value==='object'?'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+compact(value[k])).join(',')+'}':JSON.stringify(value);
function requireValue(ok){if(!ok)throw new Error('DIAGNOSTIC_MISMATCH');}
export function loadInputs(){
 const bytes=readFileSync(new URL('data/W015-Q8-real-model-protocol-v1/protocol.json',root));
 requireValue(sha(bytes)==='15cf189f478c8448b806340a083f997d3160b3f7f6e827753fd40ac7bc11db88');
 const protocol=JSON.parse(bytes),raw=readFileSync(new URL(protocol.snapshot.path,root)),snapshot=JSON.parse(raw);
 requireValue(sha(raw)===protocol.snapshot.raw_sha256&&snapshot.library_import_id===protocol.snapshot.library_import_id);
 requireValue(engineFingerprint()===protocol.engine_fingerprint&&snapshot.records.length===8);
 const pins=JSON.parse(readFileSync(new URL('service/models.json',root)));
 requireValue(compact(pins)===compact(protocol.model_pins));
 return {protocol,snapshot,pins};
}
export function validateCase(caseId,result){
 const {protocol,snapshot}=loadInputs(),test=protocol.cases.find(c=>c.id===caseId);
 requireValue(test&&test.input.public_review===false&&result?.text===test.input.text);
 requireValue(result.import_id===snapshot.library_import_id&&result.live_source_refresh===false);
 requireValue(Array.isArray(result.results)&&result.results.length===1);
 const row=result.results[0];
 requireValue(row.source_quote===test.input.text&&row.claim===test.input.text&&row.start===0&&row.end===test.input.text.length);
 requireValue(row.source_fidelity==='verbatim_token_coverage_checked'&&row.extraction_review==='model_assessed');
 for(const item of [result,row]){
  requireValue(item.job===null&&item.research_submission===undefined);
  requireValue(item.model==='qwen2.5:14b-instruct'&&item.embedding_model==='nomic-embed-text:v1.5');
  requireValue(item.model_revision===protocol.model_pins[item.model]&&item.embedding_revision===protocol.model_pins[item.embedding_model]);
  for(const key of ['status','answer','verdict'])requireValue(compact(item[key])===compact(test.expected[key]));
 }
 if(test.expected.inspection){
  const record=snapshot.records.find(r=>r.claim_id===test.expected.inspection.claim_id);
  for(const item of [result,row]){
   requireValue(compact(item.inspection)===compact(test.expected.inspection));
   requireValue(compact(item.evidence_package)===compact(record.evidence_package));
   requireValue(sha(compact(item.evidence_package))===test.expected.evidence_package_canonical_sha256);
   requireValue(item.query_relationship_review==='model_assessed'&&item.live_source_refresh===false);
  }
 }else for(const item of [result,row])requireValue(item.evidence_package==null&&item.inspection===undefined);
 return true;
}
export function fixtureBackend(snapshot,counters){
 return async(path,init={})=>{
  if(path==='/health')return {status:'ready',import_id:snapshot.library_import_id};
  if(path==='/v1/check'){
   const body=JSON.parse(init.body);counters.backend_checks++;
   if(body.public_review!==false){counters.forbidden_submissions++;throw new Error('FIXTURE_CONSENT_REJECTED');}
   requireValue(Object.keys(body).sort().join(',')==='public_review,text');
   return {status:'not_in_library'};
  }
  const match=/^\/v1\/records\/(C\d+)\?version=(\d+)&sha256=([a-f0-9]{64})$/.exec(path);
  requireValue(match&&snapshot.records.some(r=>r.claim_id===match[1]&&r.version===Number(match[2])&&r.sha256===match[3]));
  counters.record_revalidations++;return {status:'record',import_id:snapshot.library_import_id};
 };
}
export async function runOffline(emit=()=>{}){
 const {protocol,snapshot,pins}=loadInputs();
 const counts={document_embeddings:0,query_embeddings:0,audits:0,classifications:0,backend_checks:0,record_revalidations:0,forbidden_submissions:0};
 const model={chatModel:'qwen2.5:14b-instruct',embeddingModel:'nomic-embed-text:v1.5',
  chatRevision:pins['qwen2.5:14b-instruct'],embeddingRevision:pins['nomic-embed-text:v1.5'],
  async embed(texts,kind){counts[kind==='document'?'document_embeddings':'query_embeddings']+=texts.length;return texts.map(text=>{const v=Array(768).fill(0);v[text.includes('Canberra')||text.includes('national capital of Australia')?0:1]=1;return v;});},
  async json(_system,input,schema){
   if(schema.properties.coverage){counts.audits++;return {coverage:'atomic_text_preserved',reason:'Authored offline fixture'};}
   counts.classifications++;return {relationship:input.input.includes('national capital of Australia')&&input.reviewed_fact.claim.includes('Canberra')?'answers_same_question':'different_subject_or_predicate',reason:'Authored offline fixture'};
  }};
 const db=new DatabaseSync(':memory:');
 try{
  const engine=new FactEngine({snapshot,model,db,backend:'unused-offline-fixture'});
  engine.backendJson=fixtureBackend(snapshot,counts);
  await engine.initialize();requireValue(counts.document_embeddings===8);
  emit({event:'phase_complete',phase:'startup'});
  const results=[];
  for(const test of protocol.cases){
   requireValue(test.input.public_review===false);
   const result=await engine.run({...test.input});validateCase(test.id,result);
   results.push({case_id:test.id,input:test.input,result});emit({event:'phase_complete',phase:test.id});
  }
  requireValue(counts.query_embeddings===2&&counts.audits===2&&counts.classifications>0&&counts.record_revalidations===1&&counts.forbidden_submissions===0);
  return {schema_version:1,task_key:'FO-W015-Q10',kind:'actual_engine_offline_fixture_diagnostic',node:process.version,
   engine_fingerprint:engineFingerprint(),import_id:snapshot.library_import_id,counts,results,
   limits:['Deterministic model callbacks and strict snapshot backend fixture; no actual ModelClient/inference/Convex/HTTP/publication proof.',
    'No Docker/network/cache/mount/resource preflight; supervisor not wired here. No600s deadline/cleanup integration proof.',
    'Frozen exposed authored cases, shared owner/prior exposure; not factual validation or held-out accuracy.']};
 }finally{db.close();}
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 // Explicit fixture-only CLI; fixed public inputs, no model origins or arbitrary inputs.
 if(process.argv.length!==4||process.argv[2]!=='--fixture')process.exitCode=2;
 else try{const report=await runOffline(event=>process.stdout.write(JSON.stringify(event)+'\n'));
  writeFileSync(process.argv[3],JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 }catch{process.stderr.write('DIAGNOSTIC_WORKER_FAILED\n');process.exitCode=1;}
}

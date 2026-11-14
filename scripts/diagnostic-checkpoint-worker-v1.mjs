// Q14: first OFFLINE checkpoint-worker increment under accepted Q13 design.
// No CLI, live model, backend HTTP, reconciliation or public-report entry point.
import {readFileSync, lstatSync, realpathSync, readdirSync, openSync,
  writeFileSync, fsyncSync, closeSync, renameSync} from 'node:fs';
import {resolve, isAbsolute, join} from 'node:path';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {FactEngine} from '../service/engine.mjs';
import {compact, loadInputs, validateCase, fixtureBackend} from './diagnostic-worker-v2.mjs';
const root=new URL('../',import.meta.url);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const names=['01-capital.json','02-unknown.json'];
const ids=['capital-paraphrase','unknown-no-consent'];
const cap=262144;
function requireValue(ok){if(!ok)throw new Error('CHECKPOINT_WORKER_FAILED');}
function absent(path){try{lstatSync(path);return false;}catch(e){if(e.code==='ENOENT')return true;throw e;}}
function verifyBasis(){
 const bytes=readFileSync(new URL('data/W015-Q13-partial-report-design-v2/review-input.json',root));
 requireValue(sha(bytes)==='2b28e7097dc5e2ebb1bd7a85537caf8d886c546d3fc4abf6e412708bb0b68d00');
 const manifest=JSON.parse(bytes);
 requireValue(Object.keys(manifest.raw_bindings).length===69);
 for(const [file,digest] of Object.entries(manifest.raw_bindings))
  requireValue(sha(readFileSync(new URL(file,root)))===digest);
 return loadInputs();
}
// Trusted caller supplies a fresh private owned directory and reviewed code pins.
// implementationCommit is a declared caller pin, NOT authenticated Git/build attestation.
function makeSession({directory,runId,implementationCommit,workerSha256}={}){
 const {protocol,snapshot}=verifyBasis();
 requireValue(typeof directory==='string'&&isAbsolute(directory));
 requireValue(typeof runId==='string'&&/^[a-f0-9]{32}$/.test(runId));
 requireValue(typeof implementationCommit==='string'&&/^[a-f0-9]{40}$/.test(implementationCommit));
 requireValue(workerSha256===sha(readFileSync(new URL(import.meta.url))));
 const dir=resolve(directory),info=lstatSync(dir);
 requireValue(info.isDirectory()&&!info.isSymbolicLink()&&realpathSync(dir)===dir);
 requireValue(info.uid===process.getuid()&&(info.mode&0o777)===0o700&&readdirSync(dir).length===0);
 requireValue(protocol.cases.map(t=>t.id).join(',')===ids.join(','));
 let ordinal=0,failed=false;
 return Object.freeze({
  commit(caseId,result){
   try{
    requireValue(!failed&&ordinal<2&&caseId===ids[ordinal]);
    validateCase(caseId,result);
    const test=protocol.cases[ordinal];
    // Revalidate actual serialized content; toJSON cannot replace validated data silently.
    const rawResult=JSON.stringify(result);requireValue(typeof rawResult==='string');
    const serializedResult=JSON.parse(rawResult);validateCase(caseId,serializedResult);
    const envelope={schema_version:1,run_id:runId,case_id:caseId,ordinal:ordinal+1,
     input_sha256:sha(compact(test.input)),implementation_commit:implementationCommit,
     worker_raw_sha256:workerSha256,import_id:snapshot.library_import_id,result:serializedResult};
    const bytes=Buffer.from(JSON.stringify(envelope)+'\n','utf8');requireValue(bytes.length<=cap);
    const final=join(dir,names[ordinal]),temp=final+'.tmp';
    requireValue(absent(final));
    let fd;
    try{fd=openSync(temp,'wx',0o600);writeFileSync(fd,bytes);fsyncSync(fd);}
    finally{if(fd!==undefined)closeSync(fd);}
    // One trusted writer/fresh directory only: ordinary rename is NOT hostile no-clobber.
    requireValue(absent(final));renameSync(temp,final);
    ordinal++;
    return Object.freeze({case_id:caseId,ordinal,bytes:bytes.length,sha256:sha(bytes)});
   }catch{failed=true;throw new Error('CHECKPOINT_WORKER_FAILED');}
  },
 });
}
async function runCheckpoints(options,emit){
 const session=createCheckpointSession(options),{protocol,snapshot,pins}=loadInputs();
 const counts={document_embeddings:0,query_embeddings:0,audits:0,classifications:0,
  backend_checks:0,record_revalidations:0,forbidden_submissions:0};
 const model={chatModel:'qwen2.5:14b-instruct',embeddingModel:'nomic-embed-text:v1.5',
  chatRevision:pins['qwen2.5:14b-instruct'],embeddingRevision:pins['nomic-embed-text:v1.5'],
  async embed(texts,kind){counts[kind==='document'?'document_embeddings':'query_embeddings']+=texts.length;
   return texts.map(text=>{const v=Array(768).fill(0);v[text.includes('Canberra')||text.includes('national capital of Australia')?0:1]=1;return v;});},
  async json(_system,input,schema){
   if(schema.properties.coverage){counts.audits++;return {coverage:'atomic_text_preserved',reason:'Authored offline fixture'};}
   counts.classifications++;return {relationship:input.input.includes('national capital of Australia')&&input.reviewed_fact.claim.includes('Canberra')?'answers_same_question':'different_subject_or_predicate',reason:'Authored offline fixture'};
  }};
 const db=new DatabaseSync(':memory:');
 try{
  const engine=new FactEngine({snapshot,model,db,backend:'unused-offline-fixture'});
  engine.backendJson=fixtureBackend(snapshot,counts);await engine.initialize();
  requireValue(counts.document_embeddings===8);emit({event:'phase_complete',phase:'startup'});
  const saved=[];
  for(const test of protocol.cases){
   requireValue(test.input.public_review===false);
   const result=await engine.run({...test.input});
   saved.push(session.commit(test.id,result));
   emit({event:'phase_complete',phase:test.id}); // after final-file rename only
  }
  requireValue(counts.query_embeddings===2&&counts.audits===2&&counts.classifications>0&&counts.record_revalidations===1&&counts.forbidden_submissions===0);
  return {schema_version:1,task_key:'FO-W015-Q14',kind:'offline_checkpoint_worker_increment',counts,saved,
   limits:['Raw checkpoints ephemeral fixture data only; caller owns cleanup. No public projection/report or reconciler.',
    'No supervisor/deadline/crash/escaped-descendant/hostile-filesystem proof. No live model/backend/Docker/resource action.',
    'Caller-declared commit plus observed module digest, not runtime Git/build attestation. New code requires exact review.']};
 }catch{throw new Error('CHECKPOINT_WORKER_FAILED');}finally{db.close();}
}

export function createCheckpointSession(options){
 try{return makeSession(options);}catch{throw new Error('CHECKPOINT_WORKER_FAILED');}
}
export async function runOfflineCheckpoints(options,emit=()=>{}){
 try{return await runCheckpoints(options,emit);}catch{throw new Error('CHECKPOINT_WORKER_FAILED');}
}

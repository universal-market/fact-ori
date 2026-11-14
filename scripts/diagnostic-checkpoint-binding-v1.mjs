// Q16 OFFLINE single-checkpoint semantic binding/projection increment.
// Trusted caller configuration; no prefix state, filesystem or supervisor API.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {parseCheckpointBytes} from './diagnostic-checkpoint-reader-v1.mjs';
import {compact,loadInputs,validateCase} from './diagnostic-worker-v2.mjs';
const root=new URL('../',import.meta.url);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const keys=['schema_version','run_id','case_id','ordinal','input_sha256','implementation_commit','worker_raw_sha256','import_id','result'];
function requireValue(ok){if(!ok)throw 0;}
function freeze(value){if(value&&typeof value==='object'){for(const child of Object.values(value))freeze(child);Object.freeze(value);}return value;}
function basis(){
 const bytes=readFileSync(new URL('data/W015-Q15-checkpoint-reader-v1/review-input.json',root));
 requireValue(sha(bytes)==='8cc89c4d1ac481fb3903b9a73168dc7dc8e0fec96abebe1137d3a0d4d828409f');
 const bindings=JSON.parse(bytes).raw_bindings;requireValue(Object.keys(bindings).length===82);
 for(const [file,digest]of Object.entries(bindings))requireValue(sha(readFileSync(new URL(file,root)))===digest);
 requireValue(sha(readFileSync(new URL('data/FO-W015-Q15-factomaton-recipient-assessment-v1.json',root)))==='2e2e36f71b51e2d4458c62427faa92d0dc8603f06a8f6ddb6459fccc759b4c82');
 return loadInputs();
}
// Only raw Buffer input: no arbitrary objects/getters/toJSON enter validation.
// implementationCommit is trusted correlation, not Git/loaded-build attestation.
export function validateCheckpointBytes(bytes,options={}){
 try{
  const {runId,ordinal,implementationCommit,workerSha256}=options;
  requireValue(typeof runId==='string'&&/^[a-f0-9]{32}$/.test(runId));
  requireValue(Number.isInteger(ordinal)&&[1,2].includes(ordinal));
  requireValue(typeof implementationCommit==='string'&&/^[a-f0-9]{40}$/.test(implementationCommit));
  requireValue(typeof workerSha256==='string'&&/^[a-f0-9]{64}$/.test(workerSha256));
  const {protocol,snapshot}=basis();
  requireValue(workerSha256===sha(readFileSync(new URL('scripts/diagnostic-checkpoint-worker-v1.mjs',root))));
  const envelope=parseCheckpointBytes(bytes),test=protocol.cases[ordinal-1];
  requireValue(envelope!==null&&typeof envelope==='object'&&!Array.isArray(envelope));
  requireValue(Object.keys(envelope).length===keys.length&&keys.every(k=>Object.hasOwn(envelope,k)));
  requireValue(envelope.schema_version===1&&envelope.ordinal===ordinal&&envelope.case_id===test.id);
  requireValue(envelope.run_id===runId&&envelope.implementation_commit===implementationCommit);
  requireValue(envelope.worker_raw_sha256===workerSha256&&envelope.import_id===snapshot.library_import_id);
  requireValue(envelope.input_sha256===sha(compact(test.input)));
  validateCase(test.id,envelope.result); // immutable finite actual-result validator
  // Construct from pinned expected values only AFTER actual result validation.
  const expected=test.expected;
  const projection={status:expected.status,answer:expected.answer,verdict:expected.verdict,
   inspection:expected.inspection??null,evidence_package_canonical_sha256:expected.evidence_package_canonical_sha256??null,
   import_id:snapshot.library_import_id,public_review:false,live_source_refresh:false,
   projection_source:'frozen_protocol_after_validated_match'};
  const encoded=JSON.stringify(projection);requireValue(Buffer.byteLength(encoded,'utf8')<=4096);
  return freeze({case_id:test.id,state:'validated',reason_code:'validated_match',
   checkpoint_digest:{kind:'full',sha256:sha(bytes),observed_bytes:bytes.length},
   validated_projection:JSON.parse(encoded)});
 }catch{throw new Error('CHECKPOINT_BINDING_INVALID');}
}

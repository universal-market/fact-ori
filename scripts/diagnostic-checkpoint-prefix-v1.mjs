// Q17 OFFLINE finite prefix mapping. Trusted observations, not a file reader.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {validateCheckpointBytes} from './diagnostic-checkpoint-binding-v1.mjs';
const root=new URL('../',import.meta.url),ids=['capital-paraphrase','unknown-no-consent'];
const sha=b=>createHash('sha256').update(b).digest('hex');
const requireValue=ok=>{if(!ok)throw 0;};
function freeze(x){if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x;}
function basis(options){
 const bytes=readFileSync(new URL('data/W015-Q16-checkpoint-binding-v1/review-input.json',root));
 requireValue(sha(bytes)==='05182dac784e85d1c618543b6f6bad38c4efc3b701b51f19dc70ae70efc0b83c');
 const bindings=JSON.parse(bytes).raw_bindings;requireValue(Object.keys(bindings).length===88);
 for(const [file,digest]of Object.entries(bindings))requireValue(sha(readFileSync(new URL(file,root)))===digest);
 requireValue(sha(readFileSync(new URL('data/FO-W015-Q16-factomaton-recipient-assessment-v1.json',root)))==='39bfb67fbe541f0bc2656b2725c52ba96381ef0ffe9a3818d5d5fda6191fda31');
 requireValue(typeof options.leaderReaped==='boolean');
 requireValue(typeof options.runId==='string'&&/^[a-f0-9]{32}$/.test(options.runId));
 requireValue(typeof options.implementationCommit==='string'&&/^[a-f0-9]{40}$/.test(options.implementationCommit));
 requireValue(options.workerSha256===bindings['scripts/diagnostic-checkpoint-worker-v1.mjs']);
}
const row=(ordinal,state,reason,digest=null)=>({case_id:ids[ordinal-1],state,reason_code:reason,checkpoint_digest:digest,validated_projection:null});
// Caller establishes safe presence/bytes and lifecycle facts. No raw child labels.
// Only {status:'absent'}, {status:'present_invalid'}, {status:'present',bytes:Buffer}.
export function reconcileCheckpointPrefix(observations,options={}){
 try{
  basis(options);
  if(!options.leaderReaped)return freeze(ids.map((_,i)=>row(i+1,'not_reconciled','reconciliation_unavailable')));
  requireValue(Array.isArray(observations)&&observations.length===2);
  const cases=[];let prefix=true;
  for(let i=0;i<2;i++){
   const entry=observations[i],ordinal=i+1;
   requireValue(entry!==null&&typeof entry==='object'&&!Array.isArray(entry));
   requireValue(['absent','present_invalid','present'].includes(entry.status));
   const keys=Object.keys(entry);requireValue(keys.length===(entry.status==='present'?2:1)&&keys.includes('status')&&(entry.status!=='present'||keys.includes('bytes')));
   if(entry.status==='absent'){cases.push(row(ordinal,'unavailable','checkpoint_missing'));prefix=false;continue;}
   if(!prefix){cases.push(row(ordinal,'rejected','checkpoint_order_invalid'));continue;} // do not access bytes
   if(entry.status==='present_invalid'){cases.push(row(ordinal,'rejected','checkpoint_invalid'));prefix=false;continue;}
   const bytes=entry.bytes;requireValue(Buffer.isBuffer(bytes));
   const digest=bytes.length<=262144?{kind:'full',sha256:sha(bytes),observed_bytes:bytes.length}:null;
   try{cases.push(validateCheckpointBytes(bytes,{runId:options.runId,ordinal,implementationCommit:options.implementationCommit,workerSha256:options.workerSha256}));}
   catch{cases.push(row(ordinal,'rejected','checkpoint_invalid',digest));prefix=false;}
  }
  return freeze(cases);
 }catch{throw new Error('CHECKPOINT_PREFIX_INVALID');}
}

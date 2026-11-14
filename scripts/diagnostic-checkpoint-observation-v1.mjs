// Q18 OFFLINE raw observation increment; no parser, prefix or supervisor.
import {openSync,readSync,closeSync,fstatSync,lstatSync,realpathSync,constants} from 'node:fs';
import {resolve,isAbsolute,join} from 'node:path';
const names=['01-capital.json','02-unknown.json'],cap=262144;
const stable=['dev','ino','mode','uid','nlink','size','mtimeNs','ctimeNs'];
const invalid=()=>({status:'present_invalid'});
function ordinary(s){return s.isFile()&&s.uid===BigInt(process.getuid())&&s.nlink===1n;}
export function observeCheckpoint(options={}){
 // Setup/configuration errors are whole-observer failures, distinct from files.
 let dir,ordinal,readBytes;
 try{
  if(typeof options.leaderReaped!=='boolean')throw 0;
  if(!options.leaderReaped)return {status:'not_observed'}; // no directory/path access
  ({ordinal,readBytes}=options);
  if(!Number.isInteger(ordinal)||![1,2].includes(ordinal)||typeof readBytes!=='boolean')throw 0;
  if(typeof options.directory!=='string'||!isAbsolute(options.directory))throw 0;
  dir=resolve(options.directory);const info=lstatSync(dir);
  if(!info.isDirectory()||info.isSymbolicLink()||realpathSync(dir)!==dir||info.uid!==process.getuid()||(info.mode&0o777)!==0o700)throw 0;
  if(!Number.isInteger(constants.O_NOFOLLOW)||!Number.isInteger(constants.O_NONBLOCK))throw 0;
 }catch{throw new Error('CHECKPOINT_OBSERVATION_INVALID');}
 let fd,result;
 try{
  try{fd=openSync(join(dir,names[ordinal-1]),constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);}
  catch(e){if(e.code==='ENOENT')return {status:'absent'};throw e;}
  const before=fstatSync(fd,{bigint:true});if(!ordinary(before))throw 0;
  if(!readBytes)result={status:'present_unread'}; // metadata only, not a Q17 descriptor
  else{
   if(before.size>BigInt(cap))throw 0;
   const bytes=Buffer.alloc(cap+1);let count=0;
   while(count<bytes.length){const n=readSync(fd,bytes,count,bytes.length-count,null);if(n===0)break;count+=n;}
   const after=fstatSync(fd,{bigint:true});
   if(count>cap||!ordinary(after)||after.size!==BigInt(count)||stable.some(k=>before[k]!==after[k]))throw 0;
   result={status:'present',bytes:Buffer.from(bytes.subarray(0,count))};
  }
 }catch{result=invalid();}
 finally{if(fd!==undefined){try{closeSync(fd);}catch{result=invalid();}}}
 return result;
}

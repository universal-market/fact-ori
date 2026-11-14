// Q15 OFFLINE reader/parser increment. Parsed values remain UNVALIDATED.
// No semantic binding, reconciliation, public projection, supervisor or CLI.
import {openSync,readSync,closeSync,fstatSync,lstatSync,realpathSync,constants} from 'node:fs';
import {resolve,isAbsolute,join} from 'node:path';
import {TextDecoder} from 'node:util';
export const CHECKPOINT_BYTE_CAP=262144;
export const CHECKPOINT_MAX_DEPTH=16;
function reject(){throw new Error('CHECKPOINT_JSON_INVALID');}
export function parseCheckpointBytes(bytes){
 try{
  if(!Buffer.isBuffer(bytes)||bytes.length>CHECKPOINT_BYTE_CAP)reject();
  // Keep a BOM so it is rejected as non-JSON, rather than silently stripped.
  const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);let i=0;
  const ws=()=>{while(i<text.length&&' \t\r\n'.includes(text[i]))i++;};
  function string(){
   if(text[i]!== '"')reject();const start=i++;
   while(i<text.length){
    const c=text[i++];if(c==='"')return JSON.parse(text.slice(start,i));
    if(c==='\\'){if(i>=text.length)reject();i++;}
    else if(c.charCodeAt(0)<32)reject();
   }
   reject();
  }
  function value(depth){
   ws();const c=text[i];
   if(c==='{'||c==='['){
    if(depth>=CHECKPOINT_MAX_DEPTH)reject();i++;ws();
    if(c==='{'){
     const object=Object.create(null),keys=new Set();if(text[i]==='}'){i++;return object;}
     while(true){
      ws();const key=string();if(keys.has(key))reject();keys.add(key);ws();if(text[i++]!==':')reject();
      object[key]=value(depth+1);ws();const sep=text[i++];if(sep==='}')return object;if(sep!==',')reject();
     }
    }
    const array=[];if(text[i]===']'){i++;return array;}
    while(true){array.push(value(depth+1));ws();const sep=text[i++];if(sep===']')return array;if(sep!==',')reject();}
   }
   if(c==='"')return string();
   for(const [token,result]of [['true',true],['false',false],['null',null]])if(text.startsWith(token,i)){i+=token.length;return result;}
   const number=/-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/y;number.lastIndex=i;
   const match=number.exec(text);if(!match)reject();i=number.lastIndex;const result=Number(match[0]);if(!Number.isFinite(result))reject();return result;
  }
  const result=value(0);ws();if(i!==text.length)reject();return result;
 }catch{throw new Error('CHECKPOINT_JSON_INVALID');}
}
const names=['01-capital.json','02-unknown.json'];
const stable=['dev','ino','mode','uid','nlink','size','mtimeNs','ctimeNs'];
function ordinary(stat){return stat.isFile()&&stat.uid===BigInt(process.getuid())&&stat.nlink===1n;}
// Caller must establish reaped/non-escaping worker and trusted private ancestry.
// This function cannot establish those lifecycle facts from a path.
export function readCheckpointJson(directory,ordinal){
 let fd;
 try{
  if(typeof directory!=='string'||!isAbsolute(directory)||![1,2].includes(ordinal))throw 0;
  const dir=resolve(directory),info=lstatSync(dir);
  if(!info.isDirectory()||info.isSymbolicLink()||realpathSync(dir)!==dir||info.uid!==process.getuid()||(info.mode&0o777)!==0o700)throw 0;
  if(!Number.isInteger(constants.O_NOFOLLOW)||!Number.isInteger(constants.O_NONBLOCK))throw 0;
  try{fd=openSync(join(dir,names[ordinal-1]),constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);}
  catch(e){if(e.code==='ENOENT')return {status:'absent'};throw e;}
  const before=fstatSync(fd,{bigint:true});
  if(!ordinary(before)||before.size>BigInt(CHECKPOINT_BYTE_CAP))throw 0;
  const bytes=Buffer.alloc(CHECKPOINT_BYTE_CAP+1);let count=0;
  while(count<bytes.length){const n=readSync(fd,bytes,count,bytes.length-count,null);if(n===0)break;count+=n;}
  const after=fstatSync(fd,{bigint:true});
  if(count>CHECKPOINT_BYTE_CAP||!ordinary(after)||after.size!==BigInt(count)||stable.some(k=>before[k]!==after[k]))throw 0;
  const value=parseCheckpointBytes(bytes.subarray(0,count));
  return {status:'parsed_unvalidated',observed_bytes:count,value};
 }catch{throw new Error('CHECKPOINT_READ_INVALID');}
 finally{if(fd!==undefined){try{closeSync(fd);}catch{throw new Error('CHECKPOINT_READ_INVALID');}}}
}

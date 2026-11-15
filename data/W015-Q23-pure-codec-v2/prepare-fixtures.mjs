// Authored acquisition: pinned Q14 actual offline producer; no live model/backend.
import fs from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {runOfflineCheckpoints} from '../../scripts/diagnostic-checkpoint-worker-v1.mjs';
const directory=fs.mkdtempSync(join(tmpdir(),'factori-q23-'));
try {
 fs.chmodSync(directory,0o700);
 const worker=fs.readFileSync(new URL('../../scripts/diagnostic-checkpoint-worker-v1.mjs',import.meta.url));
 const report=await runOfflineCheckpoints({directory,runId:'a'.repeat(32),implementationCommit:'2df651c23a89ea8f2885ea5911557e7560403171',workerSha256:createHash('sha256').update(worker).digest('hex')});
 for(const name of ['01-capital.json','02-unknown.json']) fs.copyFileSync(join(directory,name),new URL(name,import.meta.url));
 fs.writeFileSync(new URL('producer-results.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
} finally {fs.rmSync(directory,{recursive:true,force:true});}

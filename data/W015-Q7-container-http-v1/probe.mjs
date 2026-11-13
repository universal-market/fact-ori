// Authored deterministic fixtures: container wiring evidence, never model accuracy.
import {createServer} from 'node:http';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
const pins=JSON.parse(readFileSync('/app/models.json'));
const snapshotBytes=readFileSync('/app/library.json');
const snapshot=JSON.parse(snapshotBytes);
const counts={tags:0,document_embeddings:0,query_embeddings:0,chat:0,backend_checks:0,public_submissions:0,unexpected:0};
const stub=createServer(async(req,res)=>{
 let raw='';for await(const c of req)raw+=c;
 const body=raw?JSON.parse(raw):{};let value;
 if(req.url==='/api/tags'){counts.tags++;value={models:Object.entries(pins).map(([name,digest])=>({name,digest}))};}
 else if(req.url==='/api/embed'){for(const s of body.input)counts[s.startsWith('search_query:')?'query_embeddings':'document_embeddings']++;value={embeddings:body.input.map(()=>Array(768).fill(1))};}
 else if(req.url==='/api/chat'){counts.chat++;const props=body.format.properties;value={message:{content:JSON.stringify(props.coverage?{coverage:'atomic_text_preserved',reason:'Authored stub'}:{relationship:'different_subject_or_predicate',reason:'Authored stub'})}};}
 else if(req.url==='/health')value={status:'ready',import_id:snapshot.library_import_id,public_intake:'enabled'};
 else if(req.url==='/v1/check'){counts.backend_checks++;if(body.public_review)counts.public_submissions++;value={status:'not_in_library'};}
 else{counts.unexpected++;res.statusCode=500;value={error:'unexpected_stub_route'};}
 res.setHeader('Content-Type','application/json');res.end(JSON.stringify(value));
});
await new Promise(resolve=>stub.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+stub.address().port;
Object.assign(process.env,{PORT:'8081',STATE_PATH:'/state/http.sqlite',LIBRARY_PATH:'/app/library.json',MODEL_ORIGIN:origin,EVIDENCE_ORIGIN:origin});
try{
 await import('/app/server.mjs'); // top-level await resolves after identify/index initialization
 const request=async(path,body,key)=>{const r=await fetch('http://127.0.0.1:8081'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',...(key?{'Idempotency-Key':key}:{})},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(10000)});return {status:r.status,body:await r.json()};};
 const health=await request('/health');assert.equal(health.status,200);assert.equal(health.body.status,'ready');assert.equal(health.body.import_id,snapshot.library_import_id);assert.equal(health.body.engine_revision,'d89e3de91ff22e70d8ff2aec3f8e61cb7dcd399e8aa83218444fbbc11a95654e');
 const openapi=await request('/openapi.json');assert.equal(openapi.status,200);assert.ok(openapi.body.paths['/v1/check']);
 const invalid=await request('/v1/check',{text:'A test sentence.',unexpected:true});assert.equal(invalid.status,400);
 const input={text:'The hypothetical sample is purple.',async:false,public_review:false};
 const first=await request('/v1/check',input,'W015-Q7-http-v1-unknown');assert.equal(first.status,200);assert.equal(first.body.status,'not_in_library');assert.ok(first.body.analysis_id);
 const replay=await request('/v1/check',input,'W015-Q7-http-v1-unknown');assert.deepEqual(replay,first);
 const conflict=await request('/v1/check',{...input,text:'The hypothetical sample is green.'},'W015-Q7-http-v1-unknown');assert.equal(conflict.status,409);
 assert.equal(counts.public_submissions,0);assert.equal(counts.unexpected,0);assert.equal(counts.tags,1);assert.equal(counts.document_embeddings,8);assert.equal(counts.query_embeddings,1);
 console.log('FACT_ORI_RESULT '+JSON.stringify({passed:true,node:process.version,snapshot_sha256:createHash('sha256').update(snapshotBytes).digest('hex'),import_id:snapshot.library_import_id,engine_revision:health.body.engine_revision,model_configuration:health.body.model_configuration,checks:{health:200,openapi:200,invalid:400,unknown:200,replay_identical:true,conflict:409,no_consent_submissions:0},counts}));process.exit(0);
}catch(e){console.error('FACT_ORI_PROBE_FAILURE '+e.message);process.exit(1);}

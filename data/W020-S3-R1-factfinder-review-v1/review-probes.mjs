import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.argv[2]);
const {acquireReviewCapture: acquire}=await import(pathToFileURL(resolve(root,'scripts/acquire_review_capture.mjs')));
const recorder='11111111-1111-4111-8111-111111111111', reviewer='22222222-2222-4222-8222-222222222222', owner='33333333-3333-4333-8333-333333333333', post='44444444-4444-4444-8444-444444444444';
const receipt='{"schema_version":1}\n';
const request={capture_id:'55555555-5555-4555-8555-555555555555',recorder_agent_id:recorder,reviewer_agent_id:reviewer,decision_post_id:post,decision_revision:1,reviewed_commit:'a'.repeat(40),receipt_raw_sha256:createHash('sha256').update(receipt).digest('hex')};
const copy=x=>JSON.parse(JSON.stringify(x));
function fixture(overrides={}){
 const responses={get_my_profile:{profile:{id:recorder,user_id:owner,kind:'agent'}},get_agent:{id:reviewer,user_id:owner,kind:'agent',handle:'renamed'},get_post:{id:post,kind:'post',author:{id:reviewer,user_id:owner},revision:1,title:'Decision',body:'accept; synthetic only',edited_by:null},get_post_revision:{post_id:post,revision:1,title:'Decision',body:'accept; synthetic only',edited_by:null},...overrides};
 const calls=[];const raw={};
 return {calls,raw,read:async(tool,args)=>{calls.push({tool,args});raw[tool]=JSON.stringify({result:responses[tool]});return {result_json:raw[tool]};}};
}
const passed=[];function check(name,value){assert(value,name);passed.push(name);}
const journalCases=[];
function journal(capture){journalCases.push(copy(capture));return {status:0,metadata:{authentication:'unverified_import',implementation_review:'pending',source_binding:'unchecked'}};}
let f=fixture(),r=await acquire(f.read,copy(request));
check('four sequential exact tool names',JSON.stringify(f.calls.map(x=>x.tool))===JSON.stringify(['get_my_profile','get_agent','get_post','get_post_revision']));
check('exact call arguments',JSON.stringify(f.calls.map(x=>x.args))===JSON.stringify([{}, {agent_id:reviewer},{post_id:post},{post_id:post,revision:1}]));
check('matching synthetic observations only',r.acquisition_state==='identity_revision_observed'&&r.diagnostics.length===0);
check('all original response text retained',r.capture.observations.every(o=>o.result_json===f.raw[o.tool]));
check('per-read ISO times retained',r.capture.observations.every(o=>Number.isFinite(Date.parse(o.observed_at))));
check('no authority promotion',r.receipt_authentication==='unverified_import'&&r.implementation_review==='pending');
journal(r.capture);
for(const [name,req] of [['extra field',{...request,extra:1}],['boolean revision',{...request,decision_revision:true}],['unsafe revision',{...request,decision_revision:2**53}],['uppercase UUID',{...request,capture_id:'AAAA1111-1111-4111-8111-111111111111'}],['trailing LF hash',{...request,receipt_raw_sha256:request.receipt_raw_sha256+'\n'}]]){
 f=fixture();let rejected=false;try{await acquire(f.read,req);}catch{rejected=true;}check(name+' rejected before reads',rejected&&f.calls.length===0);
}
for(const [name,over,count] of [
 ['wrong recorder',{get_my_profile:{profile:{id:reviewer,user_id:owner,kind:'agent'}}},1],
 ['human reviewer',{get_agent:{id:reviewer,user_id:owner,kind:'human'}},2],
 ['changed owner',{get_post:{id:post,kind:'post',author:{id:reviewer,user_id:recorder}}},3],
 ['wrong post',{get_post:{id:recorder,kind:'post',author:{id:reviewer,user_id:owner}}},3]]){
 f=fixture(over);r=await acquire(f.read,copy(request));check(name+' stops dependent reads',r.acquisition_state==='pending'&&f.calls.length===count);
}
f=fixture({get_post:{id:post,kind:'post',author:{id:reviewer,user_id:owner},revision:2,edited_by:{id:recorder}}});r=await acquire(f.read,copy(request));check('revision/editor mismatch pending with pinned read',r.acquisition_state==='pending'&&f.calls.length===4&&r.diagnostics.includes('decision_revision_changed')&&r.diagnostics.includes('unexpected_editor'));
f=fixture({get_post_revision:{post_id:post,revision:1,title:'Decision',body:'different',edited_by:{id:recorder}}});r=await acquire(f.read,copy(request));check('pinned text/editor diagnostics',r.diagnostics.includes('revision_text_mismatch')&&r.diagnostics.includes('unexpected_revision_editor'));
for(const [name,raw] of [['malformed','{'],['null','null'],['array','[]'],['explicit access error','{"error":"NOT_FOUND"}'],['oversize','x'.repeat(262145)]]){
 r=await acquire(async()=>({result_json:raw}),copy(request));check(name+' pending and bounded sequence',r.acquisition_state==='pending'&&r.capture.observations.length===1);
}
r=await acquire(async()=>{throw Error('synthetic-private-transport-detail');},copy(request));check('transport exception detail sanitized',!JSON.stringify(r).includes('synthetic-private-transport-detail')&&r.diagnostics[0]==='read_failed:get_my_profile');
// Negative observations deliberately assert the current defect, not desired validation.
for(const field of ['reviewed_commit','receipt_raw_sha256']){
 const req={...request,[field]:[request[field]]};f=fixture();r=await acquire(f.read,req);
 check('BUG array '+field+' accepted and four reads performed',r.acquisition_state==='identity_revision_observed'&&f.calls.length===4&&Array.isArray(r.capture[field]));
 journal(r.capture);
}
f=fixture({get_my_profile:{profile:{id:recorder,user_id:[owner],kind:'agent'}}});r=await acquire(f.read,copy(request));
check('BUG array recorder owner yields matching state with valid downstream reads',r.acquisition_state==='identity_revision_observed'&&f.calls.length===4&&Array.isArray(r.recorder_owner_id_observed));
const arrayOwner=[owner];f=fixture({get_my_profile:{profile:{id:recorder,user_id:arrayOwner,kind:'agent'}},get_agent:{id:reviewer,user_id:arrayOwner,kind:'agent'},get_post:{id:post,kind:'post',author:{id:reviewer,user_id:arrayOwner},revision:1,title:'Decision',body:'accept; synthetic only'}});
// JSON deserialization creates distinct array references, so author equality fails.
r=await acquire(f.read,copy(request));check('BUG array recorder owner accepted before downstream author failure',f.calls.length===3&&Array.isArray(r.recorder_owner_id_observed)&&r.diagnostics.includes('decision_author_mismatch'));
check('BUG array reviewer owner retained in capture',Array.isArray(r.capture.reviewer_owner_id));
journal(r.capture);
console.log(JSON.stringify({schema_version:1,subject_commit:'d1ff8838059f5afb4555be54449caee0eefeecfe',fixture_kind:'synthetic_no_authenticated_acquisition',assertion_count:passed.length,passed,journalCases,receipt,findings:['F1: Regex coercion accepts array commit/digest request fields and array observed owner IDs; request scalar validation fails to reject invalid types before reads and invalid capture reaches identity_revision_observed for commit/digest. Strict journal rejects; no authority promotion observed.']},null,2));

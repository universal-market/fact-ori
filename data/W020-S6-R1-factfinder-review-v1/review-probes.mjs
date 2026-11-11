// Synthetic output from the real pinned S4 collector; no connector or credentials.
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const {acquireReviewFrontier}=await import(pathToFileURL(resolve(process.argv[2],'scripts/acquire_review_frontier.mjs')));
const recorder='11111111-1111-4111-8111-111111111111',reviewer='22222222-2222-4222-8222-222222222222',owner='33333333-3333-4333-8333-333333333333',postId='44444444-4444-4444-8444-444444444444';
const receipt='{"schema_version":1,"decision":"accept","note":"synthetic only"}\n';
const decision={id:postId,kind:'post',author:{id:reviewer,user_id:owner},revision:1,status:null,title:'Synthetic',body:'accept',reply_count:0,edited_by:null};
const values={get_my_profile:{profile:{id:recorder,user_id:owner,kind:'agent'}},get_agent:{id:reviewer,user_id:owner,kind:'agent'},get_post:decision,get_post_revision:{post_id:postId,revision:1,title:'Synthetic',body:'accept',edited_by:null},search_posts:{items:[],next_cursor:null}};
const envelope=await acquireReviewFrontier(async tool=>({result_json:JSON.stringify({result:values[tool],fractional_metadata:0.5})}),{max_pages:1,capture_request:{capture_id:'55555555-5555-4555-8555-555555555555',recorder_agent_id:recorder,reviewer_agent_id:reviewer,decision_post_id:postId,decision_revision:1,reviewed_commit:'a'.repeat(40),receipt_raw_sha256:createHash('sha256').update(receipt).digest('hex')}});
console.log(JSON.stringify({envelope,receipt}));

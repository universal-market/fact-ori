import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.argv[2]);
const {acquireReviewFrontier:acquire,frontierFreshness:fresh}=await import(pathToFileURL(resolve(root,'scripts/acquire_review_frontier.mjs')));
const rec='11111111-1111-4111-8111-111111111111',rev='22222222-2222-4222-8222-222222222222',own='33333333-3333-4333-8333-333333333333',pid='44444444-4444-4444-8444-444444444444',rid='66666666-6666-4666-8666-666666666666';
const copy=x=>JSON.parse(JSON.stringify(x));
const request=()=>({max_pages:2,capture_request:{capture_id:'55555555-5555-4555-8555-555555555555',recorder_agent_id:rec,reviewer_agent_id:rev,decision_post_id:pid,decision_revision:1,reviewed_commit:'a'.repeat(40),receipt_raw_sha256:'b'.repeat(64)}});
const post=()=>({id:pid,kind:'post',author:{id:rev,user_id:own},revision:1,title:'Decision',body:'accept',status:null,edited_by:null,reply_count:0});
const reply=(id=rid)=>({post:{id,revision:2,author:{id:rec,user_id:own},body_summary:'apparently benign'}});
const empty=()=>({items:[],next_cursor:null});
function fixture({pages=[empty()],first=post(),last=post(),override}={}){
 const calls=[],raw=[];let page=0,posts=0;
 return {calls,raw,read:async(tool,args)=>{
  calls.push({tool,args:copy(args)});
  let value=tool==='get_my_profile'?{profile:{id:rec,user_id:own,kind:'agent'}}:tool==='get_agent'?{id:rev,user_id:own,kind:'agent'}:tool==='get_post'?(posts++===0?first:last):tool==='get_post_revision'?{post_id:pid,revision:1,title:'Decision',body:'accept',edited_by:null}:pages[page++];
  if(override){const alt=override(tool,args,value,calls.length);if(alt!==undefined)return alt;}
  const response={result_json:JSON.stringify({result:value})};raw.push(response.result_json);return response;
 }};
}
const passed=[];const check=(name,value)=>{assert(value,name);passed.push(name);};
let f=fixture(),r=await acquire(f.read,request());const normal=copy(r);
check('empty visible frontier observed without authority promotion',r.observation_state==='empty_frontier_observed'&&r.frontier_complete&&r.receipt_authentication==='unverified_import'&&r.implementation_review==='pending');
check('six ordered ordinary reads',JSON.stringify(f.calls.map(x=>x.tool))===JSON.stringify(['get_my_profile','get_agent','get_post','get_post_revision','search_posts','get_post']));
check('exact root all-depth search args',JSON.stringify(f.calls[4].args)===JSON.stringify({root_post_id:pid,max_depth:null,sort:'created_at',limit:20}));
check('S3 capture retains four observations in separate envelope',r.capture.observations.length===4&&r.observations.length===2&&!Object.hasOwn(r.capture,'frontier_complete'));
check('all raw responses retained separately',JSON.stringify([...r.capture.observations,...r.observations].map(x=>x.result_json))===JSON.stringify(f.raw));
for(const budget of [0,11,true,[2],1.5,null]){f=fixture();let threw=false;try{await acquire(f.read,{...request(),max_pages:budget});}catch{threw=true;}check('invalid budget '+JSON.stringify(budget)+' rejects before reads',threw&&f.calls.length===0);}
f=fixture({pages:[{items:[],next_cursor:'A'},{items:[],next_cursor:null}]});r=await acquire(f.read,request());
check('empty partial page continues to null completion',r.pages_read===2&&r.frontier_complete&&r.observation_state==='empty_frontier_observed'&&f.calls[5].args.cursor==='A');
f=fixture({pages:[{items:[],next_cursor:'A'}]});r=await acquire(f.read,{...request(),max_pages:1});
check('page budget preserves cursor and rereads final post pending',r.pages_read===1&&r.next_cursor==='A'&&!r.frontier_complete&&r.diagnostics.includes('frontier_page_budget_exhausted')&&f.calls.at(-1).tool==='get_post');
f=fixture({pages:[{items:[],next_cursor:'A'},{items:[],next_cursor:'B'},{items:[],next_cursor:'A'}]});r=await acquire(f.read,{...request(),max_pages:3});
check('nonadjacent cursor cycle stops pending',r.pages_read===3&&!r.frontier_complete&&r.diagnostics.includes('repeated_frontier_cursor'));
f=fixture({pages:Array.from({length:10},(_,i)=>({items:[],next_cursor:'C'+i}))});r=await acquire(f.read,{...request(),max_pages:10});check('maximum budget bounds search to ten pages',r.pages_read===10&&f.calls.filter(x=>x.tool==='search_posts').length===10&&!r.frontier_complete);
for(const [name,page] of [['missing cursor',{items:[]}],['array cursor',{items:[],next_cursor:[]}],['oversize cursor',{items:[],next_cursor:'x'.repeat(8001)}],['21 replies',{items:Array.from({length:21},()=>reply()),next_cursor:null}],['bad reply type',{items:[{post:{id:[rid]}}],next_cursor:null}],['root as reply',{items:[reply(pid)],next_cursor:null}],['duplicate same page',{items:[reply(),reply()],next_cursor:null}]]){
 r=await acquire(fixture({pages:[page]}).read,request());check(name+' pending',r.observation_state==='pending'&&!r.frontier_complete);
}
f=fixture({pages:[{items:[reply()],next_cursor:'A'},{items:[reply()],next_cursor:null}]});r=await acquire(f.read,request());check('cross-page duplicate pending',r.diagnostics.includes('malformed_or_duplicate_reply')&&!r.frontier_complete);
const counted={...post(),reply_count:1};f=fixture({first:counted,last:counted,pages:[{items:[reply()],next_cursor:null}]});r=await acquire(f.read,request());
check('third-party apparently benign reply still requires full review',r.frontier_complete&&r.observation_state==='pending'&&r.diagnostics.includes('replies_require_full_review')&&r.reply_refs[0].revision===2&&r.reply_refs[0].author_agent_id===rec);
for(const [name,last] of [['revision',{...post(),revision:2}],['title',{...post(),title:'new'}],['body',{...post(),body:'withdrawn'}],['author',{...post(),author:{id:rec,user_id:own}}],['owner',{...post(),author:{id:rev,user_id:rec}}],['editor',{...post(),edited_by:{id:rec}}],['status',{...post(),status:'done'}]]){
 r=await acquire(fixture({last}).read,request());check('final '+name+' drift pending',r.observation_state==='pending'&&r.diagnostics.includes('decision_changed_during_frontier'));
}
for(const count of [1,true,-1,null]){r=await acquire(fixture({last:{...post(),reply_count:count}}).read,request());check('bad/changed count '+JSON.stringify(count)+' pending',r.diagnostics.includes('reply_count_changed_or_inconsistent')&&r.observation_state==='pending');}
r=await acquire(fixture({first:counted,last:counted}).read,request());check('stable count but omitted replies pending',r.diagnostics.includes('reply_count_changed_or_inconsistent'));
for(const [name,response] of [['access',{result_json:'{"error":"DENIED"}',is_error:true}],['nested access',{result_json:'{"result":{"error":"DENIED"}}'}],['malformed',{result_json:'{'}],['oversize',{result_json:'x'.repeat(262145)}]]){
 f=fixture({override:tool=>tool==='search_posts'?response:undefined});r=await acquire(f.read,request());check(name+' search failure pending',!r.frontier_complete&&r.observation_state==='pending');
}
f=fixture({override:tool=>{if(tool==='search_posts')throw Error('synthetic-private-detail');}});r=await acquire(f.read,request());check('search transport details sanitized',!JSON.stringify(r).includes('synthetic-private-detail')&&r.observation_state==='pending');
f=fixture({override:tool=>tool==='get_my_profile'?{result_json:'{}'}:undefined});r=await acquire(f.read,request());check('base identity failure skips frontier',f.calls.length===1&&r.pages_read===0);
let req=request();f=fixture({override:()=>{req.max_pages=10;req.capture_request.decision_post_id=rid;}});r=await acquire(f.read,req);check('external request mutation cannot change copied root or budget',f.calls[4].args.root_post_id===pid&&r.capture.decision_post_id===pid);
const now=Date.parse(normal.finished_at);check('explicit caller age bound fits valid observations',fresh(normal,now,10000).freshness==='within_caller_age_bound');
check('stale envelope pending',fresh(normal,now+20000,10000).freshness==='pending');
check('future envelope pending',fresh(normal,now-20000,10000).freshness==='pending');
for(const [name,mutate] of [['missing start',x=>x.started_at=null],['invalid finish',x=>x.finished_at='bad-time'],['old base read',x=>x.capture.observations[0].observed_at='2000-01-01T00:00:00Z'],['old frontier read',x=>x.observations[0].observed_at='2000-01-01T00:00:00Z'],['inverted',x=>x.started_at=new Date(now+1).toISOString()]]){let x=copy(normal);mutate(x);check(name+' freshness pending',fresh(x,now,10000).freshness==='pending');}
for(const [n,a] of [[now,true],[now,-1],[0.5,1000]]){let threw=false;try{fresh(normal,n,a);}catch{threw=true;}check('invalid freshness policy '+n+'/'+a+' rejected',threw);}
check('freshness grants no authority',fresh(normal,now,10000).implementation_review==='pending'&&fresh(normal,now,10000).receipt_authentication==='unverified_import');
console.log(JSON.stringify({schema_version:1,subject_commit:'368f3aa12cce5f671a119763bc3429d540f88350',fixture_kind:'synthetic_no_authenticated_acquisition',assertion_count:passed.length,passed,normal_envelope:normal,findings:[]},null,2));

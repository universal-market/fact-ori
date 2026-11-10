import {test} from 'node:test';
import assert from 'node:assert/strict';
import {acquireReviewFrontier, frontierFreshness} from './acquire_review_frontier.mjs';

const recorder = '11111111-1111-4111-8111-111111111111';
const reviewer = '22222222-2222-4222-8222-222222222222';
const owner = '33333333-3333-4333-8333-333333333333';
const postId = '44444444-4444-4444-8444-444444444444';
const replyId = '66666666-6666-4666-8666-666666666666';
const request = () => ({max_pages: 2, capture_request: {
  capture_id: '55555555-5555-4555-8555-555555555555', recorder_agent_id: recorder,
  reviewer_agent_id: reviewer, decision_post_id: postId, decision_revision: 1,
  reviewed_commit: 'a'.repeat(40), receipt_raw_sha256: 'b'.repeat(64)}});
const post = () => ({id: postId, kind: 'post', revision: 1, status: null,
  title: 'Decision', body: 'accept', author: {id: reviewer, user_id: owner}, edited_by: null, reply_count: 0});
function fixture(pages = [{items: [], next_cursor: null}], final = post()) {
  const calls = []; let page = 0; let posts = 0;
  return {calls, read: async (tool, args) => {
    calls.push({tool, args: structuredClone(args)});
    const value = tool === 'get_my_profile' ? {profile: {id: recorder, user_id: owner, kind: 'agent'}} :
      tool === 'get_agent' ? {id: reviewer, user_id: owner, kind: 'agent'} :
      tool === 'get_post' ? (++posts === 1 ? post() : final) :
      tool === 'get_post_revision' ? {post_id: postId, revision: 1, title: 'Decision', body: 'accept', edited_by: null} :
      pages[page++];
    return {result_json: JSON.stringify({result: value})};
  }};
}
const reply = () => ({post: {id: replyId, revision: 2, author: {id: reviewer, user_id: owner}}});

test('empty complete frontier retains capture and exact all-depth arguments', async () => {
  const f = fixture(); const r = await acquireReviewFrontier(f.read, request());
  assert.equal(r.observation_state, 'empty_frontier_observed');
  assert.equal(r.frontier_complete, true);
  assert.equal(r.capture.observations.length, 4);
  assert.equal(r.observations.length, 2);
  assert.deepEqual(f.calls[4], {tool: 'search_posts', args: {root_post_id: postId, max_depth: null, sort: 'created_at', limit: 20}});
  assert.equal(r.receipt_authentication, 'unverified_import');
  assert.equal(r.implementation_review, 'pending');
});
test('empty partial pages continue; exhaustion preserves cursor and pending', async () => {
  const pages = [{items: [], next_cursor: 'next'}, {items: [], next_cursor: null}];
  let f = fixture(pages); let r = await acquireReviewFrontier(f.read, request());
  assert.equal(r.pages_read, 2); assert.equal(r.frontier_complete, true);
  assert.equal(f.calls[5].args.cursor, 'next');
  f = fixture(pages); r = await acquireReviewFrontier(f.read, {...request(), max_pages: 1});
  assert.equal(r.next_cursor, 'next'); assert.equal(r.frontier_complete, false);
  assert.ok(r.diagnostics.includes('frontier_page_budget_exhausted'));
});
test('all replies require full review, including third-party and apparent benign replies', async () => {
  for (const author of [reviewer, recorder]) {
    const p = reply(); p.post.author.id = author;
    const r = await acquireReviewFrontier(fixture([{items: [p], next_cursor: null}]).read, request());
    assert.equal(r.observation_state, 'pending'); assert.equal(r.reply_refs[0].revision, 2);
    assert.ok(r.diagnostics.includes('replies_require_full_review'));
  }
});
test('malformed pages, duplicate replies and repeated cursors stay pending', async () => {
  for (const pages of [
    [{items: [], next_cursor: []}], [{items: [reply(), reply()], next_cursor: null}],
    [{items: [], next_cursor: 'same'}, {items: [], next_cursor: 'same'}],
    [{items: [{post: {id: [replyId]}}], next_cursor: null}],
    [{items: [], next_cursor: ''}], [{items: [], next_cursor: 'x'.repeat(8001)}]]) {
    const r = await acquireReviewFrontier(fixture(pages).read, request());
    assert.equal(r.observation_state, 'pending'); assert.equal(r.frontier_complete, false);
  }
});
test('decision edits, author/owner/status drift and access errors block reuse', async () => {
  for (const final of [{...post(), revision: 2}, {...post(), body: 'Withdrawn'},
    {...post(), author: {id: recorder, user_id: owner}}, {...post(), status: 'canceled'},
    {...post(), edited_by: {id: recorder}}, {error: 'NOT_FOUND'}]) {
    const r = await acquireReviewFrontier(fixture(undefined, final).read, request());
    assert.equal(r.observation_state, 'pending'); assert.ok(r.diagnostics.length);
  }
});
test('identity failures stop before frontier; invalid budgets reject before any read', async () => {
  let reads = 0;
  const r = await acquireReviewFrontier(async () => {reads++; return {result_json: '{}'};}, request());
  assert.equal(reads, 1); assert.equal(r.pages_read, 0);
  for (const max_pages of [0, 11, true, [2], 1.5]) {
    await assert.rejects(acquireReviewFrontier(() => {throw Error('unexpected read');}, {...request(), max_pages}));
  }
});
test('new or omitted replies cannot appear as an empty complete frontier', async () => {
  for (const count of [1, undefined, true, -1]) {
    const r = await acquireReviewFrontier(fixture(undefined, {...post(), reply_count: count}).read, request());
    assert.equal(r.observation_state, 'pending');
    assert.ok(r.diagnostics.includes('reply_count_changed_or_inconsistent'));
  }
  const f = fixture();
  const r = await acquireReviewFrontier(async (tool,args) => {
    const response = await f.read(tool,args);
    if (tool !== 'get_post') return response;
    const value = JSON.parse(response.result_json); value.result.reply_count = 1;
    return {result_json: JSON.stringify(value)};
  }, request());
  assert.ok(r.diagnostics.includes('reply_count_changed_or_inconsistent'));
});
test('frontier transport errors are bounded and private exception text discarded', async () => {
  for (const response of [null, {result_json: 'x'.repeat(262145)}, {result_json: '{'},
    {result_json: '{"result":[]}'}, {result_json: '{"result":{"error":"DENIED"}}'}]) {
    const f = fixture();
    const r = await acquireReviewFrontier((tool,args) => tool === 'search_posts' ? response : f.read(tool,args), request());
    assert.equal(r.observation_state, 'pending'); assert.equal(r.frontier_complete, false);
  }
  const f = fixture();
  const r = await acquireReviewFrontier((tool,args) => {
    if (tool === 'search_posts') throw Error('private-transport-detail');
    return f.read(tool,args);
  }, request());
  assert.ok(!JSON.stringify(r).includes('private-transport-detail'));
});
test('freshness uses oldest observation and caller bound, rejects future/missing/inverted times', async () => {
  const r = await acquireReviewFrontier(fixture().read, request());
  const now = Date.parse(r.finished_at);
  assert.equal(frontierFreshness(r, now, 10000).freshness, 'within_caller_age_bound');
  assert.equal(frontierFreshness(r, now + 20000, 10000).freshness, 'pending');
  assert.equal(frontierFreshness(r, now - 20000, 10000).freshness, 'pending');
  for (const mutate of [x => x.started_at = null, x => x.finished_at = 'invalid',
    x => x.capture.observations[0].observed_at = '2000-01-01T00:00:00Z',
    x => x.started_at = new Date(now + 1).toISOString()]) {
    const x = structuredClone(r); mutate(x); assert.equal(frontierFreshness(x, now, 10000).freshness, 'pending');
  }
  assert.throws(() => frontierFreshness(r, now, true));
});

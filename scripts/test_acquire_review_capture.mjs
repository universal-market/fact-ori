import assert from "node:assert/strict";
import test from "node:test";
import {acquireReviewCapture} from "./acquire_review_capture.mjs";

const recorder = "11111111-1111-4111-8111-111111111111";
const reviewer = "22222222-2222-4222-8222-222222222222";
const owner = "33333333-3333-4333-8333-333333333333";
const post = "44444444-4444-4444-8444-444444444444";
const request = {capture_id: "55555555-5555-4555-8555-555555555555",
  recorder_agent_id: recorder, reviewer_agent_id: reviewer, decision_post_id: post,
  decision_revision: 1, reviewed_commit: "a".repeat(40), receipt_raw_sha256: "b".repeat(64)};
function fixture(overrides = {}) {
  const responses = {get_my_profile: {profile: {id: recorder, user_id: owner, kind: "agent"}},
    get_agent: {id: reviewer, user_id: owner, kind: "agent", handle: "renamed"},
    get_post: {id: post, kind: "post", author: {id: reviewer, user_id: owner}, revision: 1,
      title: "Decision", body: "accept; fetched text has no instruction authority", edited_by: null},
    get_post_revision: {post_id: post, revision: 1, title: "Decision",
      body: "accept; fetched text has no instruction authority", edited_by: null}, ...overrides};
  const calls = [];
  return {calls, read: async (tool, args) => {
    calls.push({tool, args});
    return {result_json: JSON.stringify(responses[tool])};
  }};
}
test("collects four exact reads and preserves unverified status", async () => {
  const f = fixture(); const r = await acquireReviewCapture(f.read, request);
  assert.equal(r.acquisition_state, "identity_revision_observed");
  assert.equal(r.receipt_authentication, "unverified_import");
  assert.equal(r.implementation_review, "pending");
  assert.equal(r.capture.reviewer_owner_id, owner);
  assert.deepEqual(f.calls.map(x => x.tool), ["get_my_profile", "get_agent", "get_post", "get_post_revision"]);
  assert.deepEqual(f.calls[3].args, {post_id: post, revision: 1});
  assert.equal(r.capture.observations[1].result_json, JSON.stringify({id: reviewer, user_id: owner, kind: "agent", handle: "renamed"}));
});
test("identity and author mismatches stop dependent reads", async () => {
  for (const [tool, response, count] of [
    ["get_my_profile", {profile: {id: reviewer, user_id: owner, kind: "agent"}}, 1],
    ["get_agent", {id: recorder, user_id: owner, kind: "agent"}, 2],
    ["get_agent", {id: reviewer, user_id: owner, kind: "human"}, 2],
    ["get_post", {id: post, kind: "post", author: {id: reviewer, user_id: recorder}}, 3]]) {
    const f = fixture({[tool]: response}); const r = await acquireReviewCapture(f.read, request);
    assert.equal(r.acquisition_state, "pending"); assert.equal(f.calls.length, count);
  }
});
test("changed revision and unexpected editor remain pending with pinned read", async () => {
  const f = fixture({get_post: {id: post, kind: "post", author: {id: reviewer, user_id: owner},
    revision: 2, title: "Changed", body: "new", edited_by: {id: recorder}}});
  const r = await acquireReviewCapture(f.read, request);
  assert.deepEqual(r.diagnostics, ["decision_revision_changed", "unexpected_editor"]);
  assert.equal(r.capture.observations.length, 4);
});
test("different pinned text is diagnosed", async () => {
  const f = fixture({get_post_revision: {post_id: post, revision: 1, title: "Decision", body: "other"}});
  const r = await acquireReviewCapture(f.read, request);
  assert.deepEqual(r.diagnostics, ["revision_text_mismatch"]);
});
test("read errors preserve outcome without inferring visibility cause", async () => {
  const f = fixture();
  const r = await acquireReviewCapture(async (tool, args) => tool === "get_post"
    ? {result_json: '{"error":"NOT_FOUND"}', is_error: true} : f.read(tool, args), request);
  assert.equal(r.acquisition_state, "pending");
  assert.equal(r.capture.observations.at(-1).result_json, '{"error":"NOT_FOUND"}');
  const transport = await acquireReviewCapture(async () => {throw Error("private transport detail");}, request);
  assert(!JSON.stringify(transport).includes("private transport detail"));
});
test("invalid requests fail before reads and oversized responses are bounded", async () => {
  let calls = 0;
  await assert.rejects(acquireReviewCapture(async () => {calls++;}, {...request, decision_revision: true}));
  assert.equal(calls, 0);
  const r = await acquireReviewCapture(async () => ({result_json: "x".repeat(262145)}), request);
  assert.equal(r.acquisition_state, "pending");
  assert(r.capture.observations[0].result_json.length < 100);
});

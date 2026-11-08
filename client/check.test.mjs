import test from "node:test";
import assert from "node:assert/strict";
import { checkText } from "./check.mjs";
const id = "00000000-0000-4000-8000-000000000001";
const response = (body, status = 200) =>
  new Response(JSON.stringify(body), { status });
test("client follows only bounded local analysis paths, preserving explicit consent", async () => {
  const calls = [];
  const result = await checkText("https://example.test", "Some claim", {
    publicReview: true,
    requestKey: "client-one",
    intervalMs: 0,
    fetchImpl: async (url, init) => {
      calls.push({ url: String(url), init });
      return calls.length === 1
        ? response({ id, poll_url: `/v1/checks/${id}` }, 202)
        : response({
            id,
            status: "complete",
            result: { status: "not_in_library", job: { id: "research" } },
          });
    },
  });
  assert.equal(result.analysis_id, id);
  assert.equal(result.job.id, "research");
  assert.equal(JSON.parse(calls[0].init.body).public_review, true);
  assert.equal(calls[0].init.headers["Idempotency-Key"], "client-one");
  assert.equal(calls[1].url, `https://example.test/v1/checks/${id}`);
});
test("client rejects credential-bearing origins and cross-origin polling instructions", async () => {
  await assert.rejects(
    checkText("https://user:secret@example.test", "text"),
    /without credentials/,
  );
  let calls = 0;
  await assert.rejects(
    checkText("https://example.test", "text", {
      fetchImpl: async () => {
        calls++;
        return response({ poll_url: "https://other.test/private" }, 202);
      },
    }),
    /Invalid analysis/,
  );
  assert.equal(calls, 1);
});
test("failed analysis is explicit and deadlines return resumable progress", async () => {
  let n = 0;
  await assert.rejects(
    checkText("https://example.test", "text", {
      intervalMs: 0,
      fetchImpl: async () =>
        ++n === 1
          ? response({ poll_url: `/v1/checks/${id}` }, 202)
          : response({ status: "failed", error: "uncertain extraction" }),
    }),
    /uncertain extraction/,
  );
  const pending = await checkText("https://example.test", "text", {
    deadlineMs: 0,
    fetchImpl: async () =>
      response({ poll_url: `/v1/checks/${id}`, status: "processing" }, 202),
  });
  assert.equal(pending.deadline_reached, true);
});

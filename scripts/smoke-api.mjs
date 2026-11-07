import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const base = process.env.CONVEX_SITE_URL ?? "http://127.0.0.1:3211";
assert.ok(["127.0.0.1", "localhost", "[::1]"].includes(new URL(base).hostname),
  "Run this mutating smoke check against a local development backend");
const catalog = JSON.parse(readFileSync(new URL("../data/query-catalog.json", import.meta.url)));

async function readJson(response) {
  const body = await response.json();
  assert.equal(body.implementation_review, "pending");
  assert.equal(body.implementation_provenance.binding_state, "unconfigured");
  assert.equal(body.implementation_provenance.source, null);
  assert.equal(body.implementation_provenance.build, null);
  assert.deepEqual(body.implementation_provenance.review_receipts, []);
  assert.equal(body.implementation_provenance.historical_receipts_loaded, false);
  return body;
}

async function check(body, key) {
  const response = await fetch(`${base}/v1/check`, { method: "POST",
    headers: { "Content-Type": "application/json", ...(key ? { "Idempotency-Key": key } : {}) },
    body: JSON.stringify(body) });
  return { code: response.status, body: await readJson(response) };
}

const health = await readJson(await fetch(`${base}/health`));
assert.equal(health.status, "ready");
const events = JSON.parse(readFileSync(new URL("../data/curation-events.json", import.meta.url)));
assert.equal(health.claims, new Set(events.curation_events.map((event) => event.claim_id)).size);
let exactCount = 0;
for (const route of catalog.routes) {
  for (const text of route.questions) {
    const result = await check({ text });
    assert.equal(result.code, 200);
    if (route.kind === "clarify") {
      assert.equal(result.body.status, "needs_clarification");
      assert.equal(result.body.answer, null);
    } else {
      assert.equal(result.body.evidence_package.claim_id, route.claim_id);
      assert.equal(result.body.evidence_package.selected_version, route.version);
      assert.equal(result.body.inspection.sha256, route.record_sha256);
      assert.equal(result.body.status, route.claim_id === "C003" ? "abstain" : "answer");
      exactCount++;
    }
  }
}
const capital = catalog.routes.find((route) => route.claim_id === "C004");
for (const text of ["What is Australia's national capital in 1901?",
  "What is New Zealand's national capital?", "Does one litre weigh 1,000 grams?"]) {
  const result = await check({ text });
  assert.equal(result.body.status, "not_in_library");
  assert.equal(result.body.answer, null);
  assert.equal(result.body.job, null);
  assert.ok(result.body.candidates.every((candidate) => candidate.scope_match_established === false));
}
const c005 = catalog.routes.find((route) => route.claim_id === "C005");
const inspected = await readJson(await fetch(`${base}/v1/records/C005?version=1&sha256=${c005.record_sha256}`));
assert.equal(inspected.status, "record");
assert.ok(inspected.frozen_record.inference.steps.length);
assert.ok(inspected.frozen_record.excluded_scopes.length);
assert.ok(inspected.source_reviews[0].source_checks.length);
const canonical = await check({ text: inspected.frozen_record.claim });
assert.equal(canonical.body.matching, "exact_record_claim");
assert.equal(canonical.body.evidence_package.claim_id, "C005");
assert.equal((await fetch(`${base}/v1/records/C004?version=1&sha256=${"0".repeat(64)}`)).status, 409);
assert.equal((await fetch(`${base}/v1/records/C004?version=9&sha256=${capital.record_sha256}`)).status, 409);
assert.equal((await fetch(`${base}/v1/records/C004`)).status, 400);
for (const body of [{ text: "" }, { text: "x".repeat(4001) }, { text: "???" },
  { text: 42 }, { text: "question", public_review: "yes" }, { text: "question", unexpected: true }]) {
  assert.equal((await check(body)).code, 400);
}
const malformed = await fetch(`${base}/v1/check`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: "{" });
assert.equal(malformed.status, 400);
await readJson(malformed);
const text = "The Great Wall of China is visible from the Moon with the naked eye.";
const attempts = await Promise.all(Array.from({ length: 8 }, (_, index) =>
  check({ text, public_review: true }, `local-smoke-wall-${index}`)));
assert.ok(attempts.every((result) => result.code === 202 && result.body.answer === null));
const jobId = attempts[0].body.job.id;
assert.ok(attempts.every((result) => result.body.job.id === jobId));
assert.equal((await check({ text: "A different claim", public_review: true }, "local-smoke-wall-0")).code, 409);
// Valid keys only bind opted-in unresolved public intake, including after binding.
for (const body of [
  { text: "A different private claim" },
  { text: capital.questions[0], public_review: true },
  { text: catalog.routes.find((route) => route.kind === "clarify").questions[0], public_review: true },
]) {
  assert.equal((await check(body, "local-smoke-wall-0")).code, 200);
}
assert.equal((await check({ text: "Private input must not reserve a key" }, "local-smoke-consent-scope")).code, 200);
const afterPrivate = await check({ text, public_review: true }, "local-smoke-consent-scope");
assert.equal(afterPrivate.code, 202);
assert.equal(afterPrivate.body.job.id, jobId);
const job = await readJson(await fetch(`${base}/v1/jobs/${jobId}`));
assert.equal(job.text, text);
assert.equal((await fetch(`${base}/v1/jobs/invalid`)).status, 404);
console.log(JSON.stringify({ status: "passed", exact_aliases: exactCount,
  concurrent_requests: attempts.length, deduplicated_jobs: 1, job_id: jobId }));

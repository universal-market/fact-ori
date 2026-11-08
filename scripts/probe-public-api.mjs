// Read-only HTTP verification: never submits public_review=true or operator calls.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const target = new URL(process.argv[2] ?? "http://127.0.0.1:3211");
assert.ok(!target.username && !target.password && target.pathname === "/" && !target.search && !target.hash,
  "Supply only the HTTP API origin, without credentials, path or query");
assert.ok(target.protocol === "https:" || (target.protocol === "http:" &&
  ["127.0.0.1", "localhost", "[::1]"].includes(target.hostname)), "HTTPS required for a remote API");
const snapshot = JSON.parse(readFileSync(new URL("../public/library.json", import.meta.url)));
async function json(path, init) {
  const response = await fetch(new URL(path, target), { ...init, signal: AbortSignal.timeout(10000) });
  assert.equal(response.status, 200, `${path}: unexpected HTTP status ${response.status}`);
  const body = await response.json();
  assert.equal(body.implementation_review, "pending");
  return body;
}
const health = await json("/health");
assert.equal(health.status, "ready");
assert.equal(health.public_intake, process.argv.includes('--intake-enabled') ? 'enabled' : 'disabled');
assert.equal(health.import_id, snapshot.library_import_id);
assert.equal(health.claims, snapshot.records.length + snapshot.withheld.length);
for (const mapping of snapshot.exact_mappings) {
  const answer = await json("/v1/check", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: mapping.question, public_review: false }) });
  if (mapping.kind === "clarify") {
    assert.equal(answer.status, "needs_clarification");
    assert.equal(answer.answer, null);
  } else {
    const record = snapshot.records.find(r => r.claim_id === mapping.claim_id);
    assert.equal(answer.status, record.evidence_package.answer_kind === "reviewed_abstention" ? "abstain" : "answer");
    assert.equal(answer.evidence_package.claim_id, mapping.claim_id);
    assert.equal(answer.inspection.version, mapping.version);
    assert.equal(answer.inspection.sha256, mapping.sha256);
  }
}
for (const row of snapshot.records) {
  const record = await json(`/v1/records/${row.claim_id}?version=${row.version}&sha256=${row.sha256}`);
  assert.equal(record.status, "record");
  assert.deepEqual(record.frozen_record, row.record);
}
const miss = await json("/v1/check", { method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text: "Does one litre weigh 1,000 grams?", public_review: false }) });
assert.equal(miss.status, "not_in_library");
assert.equal(miss.answer, null);
assert.equal(miss.job, null);
console.log(JSON.stringify({ status: "passed", origin: target.origin,
  records: snapshot.records.length, mappings: snapshot.exact_mappings.length,
  snapshot_sha256: snapshot.snapshot_sha256, public_intake_submitted: false }));

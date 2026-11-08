import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { checkText } from "../client/check.mjs";
const origin = process.argv[2];
const baseline = JSON.parse(readFileSync(process.argv[3], "utf8"));
assert.equal(
  baseline.length,
  14,
  "A complete 14-case actual-model report is required",
);
assert.ok(
  baseline.every((r) => r.pass),
  "Actual model gate must pass before public verification",
);
const pins = JSON.parse(
  readFileSync(new URL("../service/models.json", import.meta.url)),
);
const snapshot = JSON.parse(
  readFileSync(new URL("../public/library.json", import.meta.url)),
);
const receipt = {
  origin,
  verified_at: new Date().toISOString(),
  import_id: snapshot.library_import_id,
  checks: [],
};
async function get(path, status = 200) {
  const r = await fetch(new URL(path, origin), {
    redirect: "error",
    signal: AbortSignal.timeout(30000),
  });
  assert.equal(r.status, status, path);
  return status === 200 ? r.json() : null;
}
const health = await get("/health");
assert.equal(health.status, "ready");
assert.equal(health.semantic_search, true);
assert.equal(health.claim_decomposition, true);
assert.equal(health.public_intake, "enabled");
assert.equal(health.import_id, snapshot.library_import_id);
assert.ok(pins[health.chat_model]);
receipt.health = health;
const spec = await get("/openapi.json");
assert.equal(spec.openapi, "3.1.0");
assert.ok(spec.paths["/v1/jobs/{id}"]);
receipt.checks.push("public_openapi");
for (const name of [
  "false-capital",
  "wrong-medium",
  "unresolved-ballots",
  "paragraph",
  "compound",
]) {
  const row = baseline.find((r) => r.id === name);
  const progress = await get(`/v1/checks/${row.analysis_id}`);
  assert.equal(progress.status, "complete");
  assert.deepEqual(
    progress.result.results.map((r) => r.status),
    row.actual,
  );
  receipt.checks.push(`public_analysis:${name}`);
}
const paragraph = await checkText(
  origin,
  "Canberra is Australia's capital. A liter contains 500 milliliters.",
  {
    requestKey: `public-paragraph-verification-${health.engine_revision.slice(0, 16)}`,
  },
);
assert.deepEqual(
  paragraph.results.map((r) => r.status),
  ["answer", "contradicted"],
);
for (const result of paragraph.results) {
  assert.equal(result.model_revision, pins[health.chat_model]);
  const pin = result.inspection;
  const record = await get(
    `/v1/records/${pin.claim_id}?version=${pin.version}&sha256=${pin.sha256}`,
  );
  assert.equal(record.status, "record");
}
receipt.paragraph = {
  analysis_id: paragraph.analysis_id,
  statuses: paragraph.results.map((r) => r.status),
  pins: paragraph.results.map((r) => r.inspection),
};
receipt.checks.push("actual_public_paragraph_post_and_pinned_evidence");
const researchCase = baseline.find((r) => r.id === "research-intake");
const expectedJob = researchCase.details[0].job;
assert.ok(expectedJob?.id);
const research = await checkText(origin, researchCase.text, {
  publicReview: true,
  requestKey: `public-research-verification-${health.engine_revision.slice(0, 12)}-${expectedJob.id}`,
});
assert.equal(research.status, "not_in_library");
assert.equal(research.job.id, expectedJob.id);
const job = await get(`/v1/jobs/${research.job.id}`);
assert.ok(expectedJob.tilori_post_id);
assert.equal(job.tilori_post_id, expectedJob.tilori_post_id);
assert.equal(job.progress_source, "tilori_post");
assert.ok(job.post_revision >= 2);
assert.equal(job.progress_recorded_by, "@adrian.factomaton");
receipt.research = { analysis_id: research.analysis_id, job };
receipt.checks.push("actual_public_opt_in_dedup_and_reconciled_tilori_status");
for (const path of [
  "/",
  "/api/query",
  "/api/mutation",
  "/api/action",
  "/admin",
  "/dashboard",
])
  await get(path, 404);
receipt.checks.push("admin_routes_withheld");
receipt.status = "passed";
if (process.argv[4])
  writeFileSync(process.argv[4], JSON.stringify(receipt, null, 2) + "\n");
console.log(
  JSON.stringify({ status: receipt.status, checks: receipt.checks, origin }),
);

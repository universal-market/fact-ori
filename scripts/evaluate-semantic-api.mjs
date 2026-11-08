import assert from "node:assert/strict";
import { writeFileSync } from "node:fs";
const origin = process.argv[2] ?? "http://localhost:8081";
const outputPath = process.argv[3]?.startsWith("--") ? undefined : process.argv[3];
import { evaluationContract, contractMetadata, evaluationSnapshot } from "./semantic-report.mjs";
const contract = evaluationContract(process.argv.find(a => a.startsWith("--contract="))?.split("=")[1]);
evaluationSnapshot(contract); // Pin actual reviewed snapshot bytes before any request.
const cases = contract.cases.slice();
const health = await (await fetch(origin + "/health")).json();
assert.equal(health.status, "ready");
assert.equal(health.import_id, contract.importId, "Contract library mismatch before submission");
assert.ok(health.engine_revision);
assert.ok(health.model_configuration);
// Exercise the previously failing scope and compound paths early; retain all cases.
const priority = [
  "compound",
  "wrong-year",
  "unknown",
  "paragraph",
  "false-capital",
  "false-number",
  "wrong-medium",
];
cases.sort(
  (a, b) =>
    (priority.includes(a[0]) ? priority.indexOf(a[0]) : 99) -
    (priority.includes(b[0]) ? priority.indexOf(b[0]) : 99),
);
const report = [];
for (const [id, text, expected] of cases) {
  const started = Date.now();
  let response = await fetch(origin + "/v1/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      async: true,
      ...(id === "research-intake" ? { public_review: true } : {}),
    }),
  });
  let value = await response.json();
  const analysis_id = value.id ?? null;
  if (response.status === 202) {
    const poll = value.poll_url;
    while (Date.now() - started < 600000) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      value = await (await fetch(origin + poll)).json();
      if (value.result) {
        value = value.result;
        break;
      }
      if (value.status === "failed") break;
    }
  }
  const results = value.results ?? [value];
  const actual = results.map((r) => r.status);
  const pass =
    id === "paragraph" || id === "compound"
      ? JSON.stringify(actual) === JSON.stringify(expected)
      : actual.length === 1 && expected.includes(actual[0]);
  report.push({
    id,
    text,
    expected,
    actual,
    pass,
    duration_ms: Date.now() - started,
    analysis_id,
    engine_revision: value.engine_revision ?? null,
    import_id: value.import_id ?? null,
    model_configuration: health.model_configuration,
    evaluation_contract: contractMetadata(contract),
    error: value.error ?? null,
    details: results.map((r) => ({
      claim: r.claim,
      status: r.status,
      reason: r.reason ?? null,
      inspection: r.inspection ?? null,
      model_revision: r.model_revision ?? null,
      embedding_revision: r.embedding_revision ?? null,
      job: r.job ?? null,
      extraction_audit: r.extraction_audit ?? null,
      scope_assessment: r.scope_assessment ?? null,
      assessment: r.model_assessment ?? null,
    })),
  });
  if (outputPath)
    writeFileSync(outputPath, JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report.at(-1)));
  if (!pass && !process.argv.includes("--continue-on-failure"))
    throw new Error(`Case ${id} failed; partial report checkpointed.`);
}
if (outputPath)
  writeFileSync(outputPath, JSON.stringify(report, null, 2) + "\n");
assert.ok(
  report.every((r) => r.pass),
  "Semantic acceptance cases failed",
);

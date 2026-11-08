import test from "node:test";
import assert from "node:assert/strict";
import {
  EVALUATION_CASES,
  validateSemanticReport,
} from "./semantic-report.mjs";
const binding = {
  engineRevision: "current-engine",
  importId: "current-library",
  modelConfiguration: {
    chat_model: "pinned",
    chat_revision: "chat-digest",
    embedding_model: "embedding",
    embedding_revision: "embedding-digest",
  },
};
const fresh = () =>
  EVALUATION_CASES.map(([id, text, expected]) => ({
    id,
    text,
    expected,
    actual: id === "paragraph" || id === "compound" ? expected : [expected[0]],
    pass: true,
    engine_revision: binding.engineRevision,
    import_id: binding.importId,
    model_configuration: binding.modelConfiguration,
  }));
test("complete exact-engine diagnostic report passes", () =>
  assert.equal(validateSemanticReport(fresh(), binding), true));
test("superseded and mixed engines cannot satisfy release gate", () => {
  for (const mixed of [false, true]) {
    const report = fresh();
    for (const row of mixed ? [report[0]] : report)
      row.engine_revision = "old-engine";
    assert.throws(() => validateSemanticReport(report, binding), /engine/);
  }
});
test("missing bindings, wrong library and changed models are rejected", () => {
  for (const field of ["engine_revision", "import_id", "model_configuration"]) {
    const report = fresh();
    delete report[0][field];
    assert.throws(() => validateSemanticReport(report, binding));
  }
  const report = fresh();
  report[0].model_configuration = {
    ...binding.modelConfiguration,
    chat_revision: "different",
  };
  assert.throws(() => validateSemanticReport(report, binding));
});
test("duplicate or missing expected case IDs cannot pad report length", () => {
  const report = fresh();
  report[0] = { ...report[1] };
  assert.throws(() => validateSemanticReport(report, binding), /Duplicate/);
  const replaced = fresh();
  replaced[0].id = "other-case";
  assert.throws(() => validateSemanticReport(replaced, binding), /Missing/);
});
test("truthy passes and changed inputs, labels or outcomes cannot disguise failure", () => {
  for (const patch of [
    { pass: "true" },
    { text: "other input" },
    { expected: ["answer"] },
    { actual: ["answer"] },
  ]) {
    const report = fresh();
    Object.assign(
      report.find((r) => r.id === "wrong-year"),
      patch,
    );
    assert.throws(() => validateSemanticReport(report, binding));
  }
});

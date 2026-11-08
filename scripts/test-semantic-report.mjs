import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  EVALUATION_CASES,
  validateSemanticReport,
  evaluationContract, contractMetadata, evaluationSnapshot,
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

test("approved v2 contract binds 17 cases and preserves historical v1 validation", () => {
  const contract = evaluationContract("library-growth-v2");
  assert.equal(contract.cases.length, 17);
  assert.equal(contract.cases.find(c => c[0] === "known-venus")[2][0], "answer");
  assert.equal(contract.cases.find(c => c[0] === "research-intake")[1], "What is the chemical symbol for gold?");
  assert.equal(evaluationContract().cases.length, 14);
  const old = JSON.parse(readFileSync(new URL("../public/evaluations/2026-11-08-semantic-v1.json", import.meta.url)));
  assert.equal(validateSemanticReport(old, { engineRevision: old[0].engine_revision,
    importId: old[0].import_id, modelConfiguration: old[0].model_configuration,
    contract: evaluationContract() }), true);
});
function growthReport() {
  const contract = evaluationContract("library-growth-v2");
  const bindings = { ...binding, importId: contract.importId, contract };
  const report = contract.cases.map(([id, text, expected]) => ({ id, text, expected,
    actual: ["paragraph", "compound"].includes(id) ? expected : [expected[0]], pass: true,
    engine_revision: bindings.engineRevision, import_id: bindings.importId,
    model_configuration: bindings.modelConfiguration, evaluation_contract: contractMetadata(contract) }));
  return { contract, bindings, report };
}
test("growth reports reject missing or mixed protocol and snapshot metadata", () => {
  const fresh = growthReport();
  assert.equal(validateSemanticReport(fresh.report, fresh.bindings), true);
  for (const bad of [undefined, { ...contractMetadata(fresh.contract), sha256: "forged" },
    { ...contractMetadata(fresh.contract), snapshot_sha256: "wrong" },
    { ...contractMetadata(fresh.contract), snapshot_raw_sha256: "wrong" }]) {
    const { bindings, report } = growthReport(); report[0].evaluation_contract = bad;
    assert.throws(() => validateSemanticReport(report, bindings), /contract/);
  }
});
test("growth contract cannot be redefined or reused for another library or case set", () => {
  const { bindings, report } = growthReport();
  assert.throws(() => validateSemanticReport(report, { ...bindings, importId: "other-library" }), /library/);
  const forged = structuredClone(bindings.contract); forged.cases[0][2] = ["contradicted"];
  assert.throws(() => validateSemanticReport(report, { ...bindings, contract: forged }), /Redefined/);
  report[0].text = "different claim";
  assert.throws(() => validateSemanticReport(report, bindings), /Changed input/);
  assert.throws(() => evaluationContract("unreviewed"), /Unknown/);
});
test("snapshot loader verifies reviewed raw bytes rather than trusting embedded hash fields", () => {
  const contract = evaluationContract();
  const snapshot = evaluationSnapshot(contract);
  assert.equal(snapshot.library_import_id, contract.importId);
  const dir = mkdtempSync(join(tmpdir(), "factori-contract-"));
  try {
    const path = join(dir, "snapshot.json");
    const forged = { ...snapshot, limits: ["altered content with unchanged digest fields"] };
    writeFileSync(path, JSON.stringify(forged));
    assert.throws(() => evaluationSnapshot(contract, path), /bytes mismatch/);
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

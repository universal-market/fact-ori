import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
export const EVALUATION_CASES = [
  [
    "research-intake",
    "Is Venus’s sidereal rotation retrograde?",
    ["not_in_library"],
  ],
  ["paraphrase-units", "How many ml make up a liter?", ["answer"]],
  ["paraphrase-capital", "What is the capital city of Australia?", ["answer"]],
  ["false-capital", "Australia's capital is Sydney.", ["contradicted"]],
  ["false-number", "A liter contains 500 milliliters.", ["contradicted"]],
  [
    "wrong-predicate",
    "One litre weighs 1000 grams.",
    ["not_in_library", "needs_clarification"],
  ],
  [
    "wrong-medium",
    "Light travels at exactly 299792458 metres per second in water.",
    ["not_in_library", "needs_clarification"],
  ],
  [
    "wrong-year",
    "Who won the 2016 US presidential election?",
    ["not_in_library", "needs_clarification"],
  ],
  [
    "election-paraphrase",
    "Who won the certified United States presidential election in 2020?",
    ["answer"],
  ],
  [
    "unresolved-ballots",
    "Were all ballots cast in the 2020 US presidential election valid?",
    ["abstain"],
  ],
  [
    "ambiguous-space",
    "Can you see the Great Wall of China from space?",
    ["needs_clarification"],
  ],
  ["unknown", "Do unicorns live on Mars?", ["not_in_library"]],
  [
    "paragraph",
    "Canberra is Australia's capital. A liter contains 500 milliliters. Unicorns live on Mars.",
    ["answer", "contradicted", "not_in_library"],
  ],
  [
    "compound",
    "Canberra is Australia's capital and Sydney is Australia's capital.",
    ["answer", "contradicted"],
  ],
];

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
export function evaluationContract(version = "seven-record-v1") {
  if (version === "seven-record-v1") return {
    id: version,
    sha256: sha256(JSON.stringify(EVALUATION_CASES)),
    importId: "59ca55b17bf6bfcfa0820d12a95766198581f73dae95534e17fdaa4057dc60d8",
    snapshotSha256: "c4c7c3b4bdea8c73dc75d38af8ce9c6ff246536fcc8dc3696fd26acf382c3ca6",
    snapshotRawSha256: "87cfa98822c49baf1103b5ddab02caf04402593db90ab1946bce182443d6986a",
    cases: EVALUATION_CASES,
  };
  assert.equal(version, "library-growth-v2", "Unknown evaluation contract");
  const bytes = readFileSync(new URL("./evaluation-contracts/library-growth-v2.json", import.meta.url));
  const expectedHash = "22bdbf7e82abe6880e790b27b5c93c80eb133a7e4b7f86b72e689a209c269045";
  assert.equal(sha256(bytes), expectedHash, "Approved contract bytes changed");
  const value = JSON.parse(bytes);
  assert.equal(value.schema_version, 2);
  assert.equal(value.library_import_id, "e78b021826f2b202abcc257cf1f49116cb376d004cb70ee2613a0b8e90499d53");
  assert.equal(value.snapshot_sha256, "1cf35fb47563862540b0a343cc02f65633665826c509fcea3eeb4f641bda2b23");
  assert.equal(value.cases.length, 17);
  assert.equal(new Set(value.cases.map(c => c[0])).size, 17);
  return { id: version, sha256: expectedHash, importId: value.library_import_id,
    snapshotSha256: value.snapshot_sha256,
    snapshotRawSha256: "563188b309e946ea0f2dfb5e475d12979b281bd62277694b255e6e851b391060", cases: value.cases };
}
export function contractMetadata(contract) {
  return { id: contract.id, sha256: contract.sha256, case_count: contract.cases.length,
    snapshot_sha256: contract.snapshotSha256, snapshot_raw_sha256: contract.snapshotRawSha256 };
}

export function evaluationSnapshot(contract, path = process.env.EVALUATION_SNAPSHOT_PATH ?? new URL("../public/library.json", import.meta.url)) {
  assert.deepEqual(contract, evaluationContract(contract.id), "Redefined approved contract");
  const bytes = readFileSync(path);
  assert.equal(sha256(bytes), contract.snapshotRawSha256, "Contract snapshot bytes mismatch");
  const snapshot = JSON.parse(bytes);
  assert.equal(snapshot.library_import_id, contract.importId, "Contract snapshot import mismatch");
  assert.equal(snapshot.snapshot_sha256, contract.snapshotSha256, "Contract snapshot subject mismatch");
  return snapshot;
}

export function validateSemanticReport(
  report,
  { engineRevision, importId, modelConfiguration, contract },
) {
  const cases = contract?.cases ?? EVALUATION_CASES;
  if (contract) {
    assert.deepEqual(contract, evaluationContract(contract.id), "Redefined approved contract");
    assert.equal(importId, contract.importId, "Contract library mismatch");
  }
  assert.ok(Array.isArray(report));
  assert.equal(report.length, cases.length);
  const ids = report.map((row) => row.id);
  assert.equal(new Set(ids).size, ids.length, "Duplicate case IDs");
  for (const [id, text, expected] of cases) {
    const row = report.find((row) => row.id === id);
    assert.ok(row, `Missing case ${id}`);
    assert.equal(row.text, text, `Changed input ${id}`);
    assert.deepEqual(row.expected, expected, `Changed expected labels ${id}`);
    assert.equal(row.pass, true, `Case did not strictly pass ${id}`);
    if (contract && (contract.id !== "seven-record-v1" || row.evaluation_contract !== undefined))
      assert.deepEqual(row.evaluation_contract, contractMetadata(contract), `Missing/mixed contract ${id}`);
    assert.equal(
      row.engine_revision,
      engineRevision,
      `Superseded/missing engine ${id}`,
    );
    assert.equal(row.import_id, importId, `Different library ${id}`);
    assert.deepEqual(
      row.model_configuration,
      modelConfiguration,
      `Different model configuration ${id}`,
    );
    if (id === "paragraph" || id === "compound")
      assert.deepEqual(row.actual, expected, `Invalid outcome ${id}`);
    else {
      assert.equal(row.actual.length, 1);
      assert.ok(expected.includes(row.actual[0]), `Invalid outcome ${id}`);
    }
  }
  return true;
}

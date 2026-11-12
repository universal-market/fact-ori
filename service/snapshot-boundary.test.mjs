import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { assertPublicSnapshot } from "./snapshot-boundary.mjs";
const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url)));
const library = read("../public/library.json");
const offline = read("../scripts/fixtures/c007a-v3/pending-consumer-results-v1.json");
const invalid = (value) => assert.throws(() => assertPublicSnapshot(value),
  { code: "INVALID_PUBLIC_SNAPSHOT", message: "Unsupported or malformed public evidence snapshot" });

test("current eight-record export passes unchanged; validator has no I/O dependencies", () => {
  const input = structuredClone(library), before = JSON.stringify(input);
  assert.equal(assertPublicSnapshot(input), undefined);
  assert.equal(JSON.stringify(input), before);
  assert.equal(input.records.length, 8);
});
test("actual offline seed and export reject, including forged kind/version", () => {
  for (const fixture of [offline.seed, offline.export]) {
    invalid(fixture);
    invalid({ ...fixture, kind: library.kind, schema_version: 1 });
  }
});
test("missing/unknown envelope fields, wrong types and versions reject", () => {
  for (const value of [null, [], true, 1, "snapshot"]) invalid(value);
  for (const key of Object.keys(library)) {
    const x = structuredClone(library); delete x[key]; invalid(x);
  }
  for (const [key, value] of Object.entries({
    schema_version: "1", kind: "offline_withheld_export_diagnostic",
    library_import_id: "synthetic", snapshot_sha256: "G".repeat(64),
    curation_log_sha256: null, curation_as_of: 123, implementation_review: false,
    records: {}, withheld: null, exact_mappings: "[]", limits: [4],
    not_for_publication: true,
  })) invalid({ ...library, [key]: value });
  invalid({ ...library, schema_version: 2 });
  invalid({ ...library, future_field: true });
});
test("pending rows, duplicate identities, inconsistent pins and consumed fields reject", () => {
  const mutations = [
    (x) => x.records.push(structuredClone(x.records[0])),
    (x) => x.records[0].evidence_package.state = "pending",
    (x) => x.records[0].evidence_package.selected_version++,
    (x) => x.records[0].evidence_package.claim_id = "other",
    (x) => x.records[0].evidence_package.answer_kind = "pending",
    (x) => x.records[0].evidence_package.answer = "different",
    (x) => x.records[0].record.id = "other",
    (x) => x.records[0].record.version++,
    (x) => x.records[0].record.scope = [],
    (x) => x.records[0].source_reviews = {},
    (x) => x.records[0].sha256 = "bad",
    (x) => x.records[0].version = true,
    (x) => x.records[0].version = Number.MAX_SAFE_INTEGER + 1,
    (x) => x.exact_mappings.find((m) => m.kind === "claim").version++,
    (x) => x.exact_mappings.find((m) => m.kind === "claim").claim_id = "missing",
    (x) => x.exact_mappings.find((m) => m.kind === "claim").sha256 = "a".repeat(64),
    (x) => x.exact_mappings.push(structuredClone(x.exact_mappings[0])),
    (x) => x.exact_mappings[0].kind = "pending",
    (x) => x.exact_mappings[0].clarification = null,
    (x) => x.exact_mappings[0].claim_id = "C001",
    (x) => x.withheld.push({ claim_id: "C001", state: "pending", selected_version: 1 }),
  ];
  for (const change of mutations) { const x = structuredClone(library); change(x); invalid(x); }
});
test("valid empty library and explicit withheld metadata remain representable", () => {
  const x = { ...library, records: [], exact_mappings: [], withheld: [
    { claim_id: "pending-id", state: "pending", selected_version: 1 },
    { claim_id: "unselected-id", state: "unselected", selected_version: null },
  ] };
  assertPublicSnapshot(x);
  invalid({ ...x, withheld: [...x.withheld, x.withheld[0]] });
  invalid({ ...x, withheld: [{ claim_id: "x", state: "approved", selected_version: 1 }] });
});
test("literal keys retain case/spacing; format acceptance is not authenticity", () => {
  const x = structuredClone(library);
  const original = x.exact_mappings.find((m) => m.kind === "claim");
  x.exact_mappings.push({ ...original, question: original.question.toUpperCase() });
  x.exact_mappings.push({ ...original, question: ` ${original.question} ` });
  // A coherent invented envelope still passes: hashes/curation are not authenticated.
  x.snapshot_sha256 = "0".repeat(64);
  assertPublicSnapshot(x);
  assert.equal(x.exact_mappings.at(-1).question, ` ${original.question} `);
});

// Staged format validator only: not connected to the engine or server yet.
// Structural consistency does not authenticate a snapshot or approve its facts.
const fields = new Set([
  "schema_version", "kind", "library_import_id", "curation_as_of",
  "curation_log_sha256", "records", "withheld", "exact_mappings",
  "implementation_review", "limits", "snapshot_sha256",
]);
const object = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
const text = (x) => typeof x === "string" && x.trim().length > 0;
const hash = (x) => typeof x === "string" && /^[a-f0-9]{64}$/.test(x);
const version = (x) => Number.isSafeInteger(x) && x > 0;
const fail = () => {
  const error = new Error("Unsupported or malformed public evidence snapshot");
  error.code = "INVALID_PUBLIC_SNAPSHOT";
  throw error;
};

/** Validate schema1's supported envelope and consumed identity/mapping fields.
 * Does not verify canonical hashes, authenticity, currency or curation authority.
 * No I/O, indexing, coercion, normalization, mutation or model/backend calls.
 */
export function assertPublicSnapshot(snapshot) {
  if (!object(snapshot) ||
      Object.keys(snapshot).some((key) => !fields.has(key)) ||
      [...fields].some((key) => !Object.hasOwn(snapshot, key)) ||
      snapshot.schema_version !== 1 ||
      snapshot.kind !== "static_public_evidence_snapshot" ||
      !hash(snapshot.library_import_id) || !hash(snapshot.snapshot_sha256) ||
      !hash(snapshot.curation_log_sha256) ||
      !(snapshot.curation_as_of === null || text(snapshot.curation_as_of)) ||
      !text(snapshot.implementation_review) ||
      !Array.isArray(snapshot.records) || !Array.isArray(snapshot.withheld) ||
      !Array.isArray(snapshot.exact_mappings) || !Array.isArray(snapshot.limits) ||
      !snapshot.limits.every(text)) fail();

  const records = new Map();
  for (const row of snapshot.records) {
    if (!object(row) || !text(row.claim_id) || !version(row.version) ||
        !hash(row.sha256) || records.has(row.claim_id) ||
        !object(row.record) || row.record.id !== row.claim_id ||
        row.record.version !== row.version ||
        ![row.record.claim, row.record.answer, row.record.scope].every(text) ||
        !object(row.evidence_package) ||
        row.evidence_package.claim_id !== row.claim_id ||
        row.evidence_package.state !== "approved" ||
        row.evidence_package.selected_version !== row.version ||
        row.evidence_package.answer !== row.record.answer ||
        !["supported_assertion", "reviewed_abstention"].includes(row.evidence_package.answer_kind) ||
        !Array.isArray(row.source_reviews)) fail();
    records.set(row.claim_id, row);
  }
  const withheld = new Set();
  for (const row of snapshot.withheld) {
    if (!object(row) || !text(row.claim_id) || records.has(row.claim_id) ||
        withheld.has(row.claim_id) ||
        !["pending", "reopened", "retired", "unselected"].includes(row.state) ||
        !(row.selected_version === null || version(row.selected_version))) fail();
    withheld.add(row.claim_id);
  }
  const questions = new Set();
  for (const mapping of snapshot.exact_mappings) {
    if (!object(mapping) || !text(mapping.question) || questions.has(mapping.question)) fail();
    questions.add(mapping.question);
    if (mapping.kind === "clarify") {
      if (!text(mapping.clarification) ||
          Object.keys(mapping).some((k) => !["question", "kind", "clarification"].includes(k))) fail();
    } else if (mapping.kind === "claim") {
      const row = records.get(mapping.claim_id);
      if (!row || mapping.version !== row.version || mapping.sha256 !== row.sha256 ||
          Object.keys(mapping).some((k) => !["question", "kind", "claim_id", "version", "sha256"].includes(k))) fail();
    } else fail();
  }
}

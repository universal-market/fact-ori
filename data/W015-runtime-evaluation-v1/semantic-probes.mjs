// Local runtime diagnostic only. No network, model download or persistent DB.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { FactEngine } from "../../service/engine.mjs";

const read = (p) => JSON.parse(readFileSync(new URL("../../" + p, import.meta.url)));
const fixture = read("scripts/fixtures/c007a-v3/pending-consumer-results-v1.json");
const rows = read("scripts/fixtures/c007a-v3/predicate-catalog-v1.json").routes;
const record = read("scripts/fixtures/c007a-v3/record.json");
const pending = read("scripts/fixtures/c007a-v3/pending-view-v1.json");
const results = [];
function engine(snapshot) {
  const db = new DatabaseSync(":memory:");
  let embeds = 0, classifications = 0, network = 0;
  const model = { embeddingModel: "stub", chatModel: "stub",
    embed: async (texts) => { embeds += texts.length; return texts.map(() => [1, 1]); },
    json: async () => { classifications++; return { relationship: "answers_same_question", reason: "Stub only" }; },
  };
  const value = new FactEngine({ snapshot, model, db, backend: "http://unused.invalid" });
  value.backendJson = async () => { network++; throw new Error("Network disabled in evaluation"); };
  return { value, db, counts: () => ({ embeds, classifications, network }) };
}

{
  const e = engine(fixture.seed);
  await assert.rejects(e.value.initialize(), TypeError);
  assert.equal(e.counts().network, 0);
  results.push({ case: "direct_offline_seed", initialization: "TypeError_missing_records", network: 0 });
  e.db.close();
}
{
  const e = engine(fixture.export);
  await e.value.initialize();
  const statuses = [];
  for (const r of rows.slice(0, 3)) {
    const result = await e.value.match({ claim: r.query, kind: "question" });
    assert.equal(result.status, "not_in_library"); assert.equal(result.answer, null);
    assert.deepEqual(result.candidates, []); statuses.push(result.status);
  }
  assert.equal(e.value.records.length, 0);
  assert.equal(e.counts().network, 0);
  results.push({ case: "direct_offline_export", initialized_records: 0, statuses,
    pending_routes_recognized: false, ...e.counts() });
  e.db.close();
}
{
  // Deliberate synthetic wrapper and approving backend stub, NOT real approval.
  const pkg = structuredClone(pending.claims[0]);
  pkg.state = "approved"; pkg.answer_kind = "supported_assertion"; pkg.answer = record.answer;
  const snapshot = { library_import_id: "synthetic", records: [{ claim_id: "C007a", version: 3,
    sha256: fixture.seed.withheld_claim.record_digest, record, evidence_package: pkg }],
    exact_mappings: rows.slice(0, 3).map((r) => ({ claim_id: "C007a", question: r.query })) };
  const e = engine(snapshot);
  let backend_stub_calls = 0;
  e.value.backendJson = async () => { backend_stub_calls++; return { status: "record", import_id: "synthetic" }; };
  await e.value.initialize();
  for (const r of rows.slice(0, 3)) {
    const result = await e.value.match({ claim: r.query, kind: "question" });
    assert.equal(result.status, "answer"); assert.equal(result.answer, record.answer);
    assert.notEqual(result.answer, r.proposed_answer);
  }
  results.push({ case: "synthetic_approval_and_model_backend_stubs", queries: 3,
    every_answer_equals_whole_compound: true, backend_stub_calls, live_network: 0,
    limitation: "No factual/model/curation/active deployment conclusion." });
  e.db.close();
}
console.log(JSON.stringify({ schema_version: 1, task_key: "W015-runtime-evaluation-v1",
  results, live_network: false, persistent_database: false, production_source_edited: false }, null, 2));

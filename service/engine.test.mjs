import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { FactEngine, cosine } from "./engine.mjs";
const library = JSON.parse(
  readFileSync(new URL("../public/library.json", import.meta.url)),
);
function fixture(id = "C005", assessment = {}) {
  const record = library.records.find((r) => r.claim_id === id);
  const model = {
    embeddingModel: "test",
    chatModel: "test",
    embed: async (texts) => texts.map(() => Array(768).fill(1)),
    json: async (_system, _input, schema) =>
      schema.properties.compatible
        ? { compatible: false, reason: "Material scope difference" }
        : {
            decision: "supported",
            reason: "Stored evidence supports the predicate.",
            scope_difference: "",
            ...assessment,
          },
  };
  const engine = new FactEngine({
    snapshot: { ...library, records: [record] },
    model,
    db: new DatabaseSync(":memory:"),
    backend: "http://unused",
  });
  engine.backendJson = async (path) =>
    path === "/health"
      ? { import_id: library.library_import_id }
      : { status: "record", import_id: library.library_import_id };
  return { engine, record };
}
test("dense vector cosine uses normalized direction", () => {
  assert.equal(cosine([1, 0], [2, 0]), 1);
  assert.equal(cosine([1, 0], [0, 1]), 0);
  assert.equal(cosine([0, 0], [1, 1]), 0);
});
test("ordinary questions retain exact text and source spans", async () => {
  const { engine } = fixture();
  const input = "How many ml make up a liter?";
  const claims = await engine.extract(input);
  assert.equal(claims[0].claim, input);
  assert.equal(claims[0].kind, "question");
  assert.equal(input.slice(claims[0].start, claims[0].end), input);
});
test("contradiction binds stored evidence, answer and immutable pins", async () => {
  const { engine, record } = fixture("C005", { decision: "contradicted" });
  await engine.initialize();
  const result = await engine.match({
    claim: "A litre contains 500 millilitres.",
    kind: "assertion",
  });
  assert.equal(result.status, "contradicted");
  assert.equal(result.verdict, "contradicted");
  assert.equal(result.inspection.sha256, record.sha256);
  assert.deepEqual(result.evidence_package, record.evidence_package);
});
test("abstention cannot become a contradiction or positive assertion", async () => {
  for (const decision of ["contradicted", "supported", "abstain"]) {
    const { engine } = fixture("C009", { decision });
    await engine.initialize();
    const result = await engine.match({
      claim: "An unaided sighting occurred.",
      kind: "assertion",
    });
    assert.equal(result.status, "abstain");
    assert.equal(result.verdict, "insufficient_evidence");
  }
});
test("material scope differences and unrelated predicates cannot answer", async () => {
  for (const assessment of [
    { scope_difference: "Different medium" },
    { decision: "unrelated" },
  ]) {
    const { engine } = fixture("C010", assessment);
    await engine.initialize();
    const result = await engine.match({
      claim: "Light speed in water",
      kind: "question",
    });
    assert.ok(
      ["not_in_library", "needs_clarification"].includes(result.status),
    );
    assert.equal(result.answer, null);
  }
});
test("invalid model decisions and reasons fail closed", async () => {
  for (const bad of [
    { decision: "true" },
    { reason: null },
    { scope_difference: 42 },
  ]) {
    const { engine } = fixture("C005", bad);
    await engine.initialize();
    await assert.rejects(engine.match({ claim: "Question", kind: "question" }));
  }
});
test("curation is revalidated after inference before returning an answer", async () => {
  const { engine } = fixture();
  await engine.initialize();
  engine.backendJson = async () => {
    throw new Error("withheld");
  };
  await assert.rejects(
    engine.match({ claim: "Question", kind: "question" }),
    /withheld/,
  );
});
test("compound extraction rejects invented numerical claims and missing source spans", async () => {
  for (const output of [
    {
      source_quote: "One litre and some water",
      claim: "One litre is 500 ml",
      kind: "assertion",
    },
    { source_quote: "absent", claim: "water", kind: "assertion" },
  ]) {
    const { engine } = fixture();
    engine.model.json = async () => ({ claims: [output] });
    await assert.rejects(engine.extract("One litre and some water"));
  }
});

test("repeated sentences retain distinct source offsets", async () => {
  const { engine } = fixture();
  const claims = await engine.extract("Hello. Hello.");
  assert.deepEqual(
    claims.map((c) => c.start),
    [0, 7],
  );
});
test("omitted source sentences fail explicitly instead of claiming full coverage", async () => {
  const { engine } = fixture();
  engine.model.json = async () => ({
    claims: [
      { source_quote: "Water and ice.", claim: "Water", kind: "assertion" },
    ],
  });
  await assert.rejects(
    engine.extract("Water and ice. A second fact."),
    /cover every/,
  );
});
test("research intake failure preserves the unknown result without fabricated job", async () => {
  const { engine } = fixture("C005", { decision: "unrelated" });
  await engine.initialize();
  engine.backendJson = async (path, init) => {
    if (path === "/health") return { import_id: library.library_import_id };
    if (JSON.parse(init.body).public_review) throw Error("queue full");
    return { status: "not_in_library" };
  };
  const result = await engine.run({
    text: "An unknown claim.",
    public_review: true,
  });
  assert.equal(result.status, "not_in_library");
  assert.equal(result.research_submission, "unavailable");
  assert.equal(result.job, null);
});

test("scope adjudication distinguishes contradictory values from changed conditions", async () => {
  const { engine } = fixture("C005", {
    decision: "contradicted",
    scope_difference: "Different numeric value",
  });
  const classify = engine.model.json;
  engine.model.json = async (s, i, schema) =>
    schema.properties.compatible
      ? { compatible: true, reason: "Same volume equivalence" }
      : classify(s, i, schema);
  await engine.initialize();
  assert.equal(
    (await engine.match({ claim: "One litre is 500 ml", kind: "assertion" }))
      .status,
    "contradicted",
  );
});

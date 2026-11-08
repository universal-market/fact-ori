import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import {
  FactEngine,
  cosine,
  explicitYearConflict,
  checkedVerbatimSpans,
  obscureContent,
  researchSubmissionText,
} from "./engine.mjs";
const library = JSON.parse(
  readFileSync(new URL("../public/library.json", import.meta.url)),
);
function fixture(id = "C005", assessment = {}) {
  const record = library.records.find((r) => r.claim_id === id);
  const model = {
    embeddingModel: "test",
    chatModel: "test",
    embed: async (texts) => texts.map(() => Array(768).fill(1)),
    json: async (_system, input, schema) => {
      if (schema.properties.claims)
        return {
          claims: [
            ...new Intl.Segmenter("en", { granularity: "sentence" }).segment(
              input.text,
            ),
          ].map((s) => ({
            source_quote: s.segment.trim(),
            claim: s.segment.trim(),
          })),
        };
      if (schema.properties.coverage)
        return {
          coverage: "atomic_text_preserved",
          reason: "All atomic texts preserved",
        };
      return {
        relationship: assessment.scope_difference
          ? "different_conditions_or_dates"
          : {
              supported: "supports_same_claim",
              answered: "answers_same_question",
              contradicted: "contradicts_same_claim",
              abstain: "insufficient_evidence_same_predicate",
              ambiguous: "ambiguous",
              unrelated: "different_subject_or_predicate",
            }[assessment.decision ?? "supported"],
        reason: "Stored evidence supports the predicate.",
        ...assessment,
      };
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
    { relationship: null },
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
    engine.model.json = async (_s, _i, schema) =>
      schema.properties.coverage
        ? {
            coverage: "combined_clauses_need_splitting",
            reason: "Needs splitting",
          }
        : { claims: [output] };
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
  engine.model.json = async (_s, _i, schema) =>
    schema.properties.coverage
      ? {
          coverage: "combined_clauses_need_splitting",
          reason: "Needs splitting",
        }
      : {
          claims: [
            {
              source_quote: "Water and ice.",
              claim: "Water and ice.",
              kind: "assertion",
            },
          ],
        };
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

test("explicit relationship separates conflicting values from changed conditions", async () => {
  const { engine } = fixture("C005", { decision: "contradicted" });
  await engine.initialize();
  assert.equal(
    (await engine.match({ claim: "One litre is 500 ml", kind: "assertion" }))
      .status,
    "contradicted",
  );
});

test("ambiguous validity cannot become supported through scope compatibility", async () => {
  const { engine } = fixture("C004", { decision: "ambiguous" });
  engine.model.json = async () => ({
    relationship: "ambiguous",
    reason: "Two possible capitals",
  });
  await engine.initialize();
  assert.equal(
    (
      await engine.match({
        claim: "The Australian capital might be Canberra or Sydney.",
        kind: "assertion",
      })
    ).status,
    "needs_clarification",
  );
});
test("full quoted span cannot hide omitted clauses or altered predicates", async () => {
  for (const text of [
    "Canberra is Australia's capital and Sydney is Australia's capital.",
    "Canberra is Australia's capital, Sydney is Australia's capital.",
    "Canberra is Australia's capital while Sydney is not Australia's capital.",
  ]) {
    const { engine } = fixture();
    let extracted = false;
    engine.model.json = async (_s, _i, schema) =>
      schema.properties.claims
        ? ((extracted = true),
          {
            claims: [
              { source_quote: text, claim: "Canberra is Australia's capital." },
            ],
          })
        : {
            coverage: "combined_clauses_need_splitting",
            reason: "Omitted or altered second predicate",
          };
    await assert.rejects(engine.extract(text), /verbatim/);
    assert.equal(extracted, true);
  }
});

test("verbatim false assertions and unanswered questions need no invented answer", async () => {
  const { engine } = fixture();
  for (const text of [
    "A litre contains 500 millilitres.",
    "Who won in 2016?",
  ]) {
    const result = await engine.extract(text);
    assert.equal(result[0].claim, text);
    assert.equal(result[0].extraction_audit.coverage, "atomic_text_preserved");
  }
});

test("explicit dated-claim mismatch cannot inherit a contradictory or supported answer", async () => {
  assert.deepEqual(
    explicitYearConflict(
      "Who won in 2016?",
      "The winner of the 2020 election.",
    ),
    { requested_years: ["2016"], reviewed_years: ["2020"] },
  );
  assert.equal(
    explicitYearConflict("Who won in 2020?", "The 2020 election."),
    null,
  );
  assert.equal(
    explicitYearConflict(
      "One litre is 2000 millilitres",
      "One litre equals 1000 millilitres",
    ),
    null,
  );
  assert.ok(
    explicitYearConflict(
      "Who won the 1776 election?",
      "The winner of the 2020 election",
    ),
  );
  const { engine } = fixture("C001", { decision: "contradicted" });
  await engine.initialize();
  engine.model.json = async () => {
    throw Error("Mismatched dated record must not reach classification");
  };
  const result = await engine.match({
    claim: "Who won the 2016 US presidential election?",
    kind: "question",
  });
  assert.equal(result.status, "not_in_library");
  assert.equal(result.answer, null);
  assert.equal(result.scope_guards.length, 1);
});

test("different conditions do not hide a later matching package", async () => {
  const { engine } = fixture();
  engine.snapshot = {
    ...library,
    records: [
      library.records.find((r) => r.claim_id === "C010"),
      library.records.find((r) => r.claim_id === "C005"),
    ],
  };
  let n = 0;
  engine.model.json = async () => ({
    relationship:
      ++n === 1 ? "different_conditions_or_dates" : "answers_same_question",
    reason: "Evaluate each candidate separately",
  });
  await engine.initialize();
  const result = await engine.match({
    claim: "How many millilitres in a litre?",
    kind: "question",
  });
  assert.equal(n, 2);
  assert.equal(result.status, "answer");
  assert.equal(result.inspection.claim_id, "C005");
});
test("uncovered conditions are missing coverage, eligible for opted-in research", async () => {
  const { engine } = fixture("C010", {
    relationship: "different_conditions_or_dates",
  });
  await engine.initialize();
  const result = await engine.match({
    claim: "Speed in water?",
    kind: "question",
  });
  assert.equal(result.status, "not_in_library");
  assert.equal(result.answer, null);
});

test("valid atomic clause quotes need not each contain the entire compound sentence", async () => {
  const { engine } = fixture();
  const text =
    "Canberra is Australia's capital and Sydney is Australia's capital.";
  let audits = 0;
  engine.model.json = async (_s, _i, schema) =>
    schema.properties.claims
      ? {
          claims: [
            {
              source_quote: "Canberra is Australia's capital",
              claim: "Canberra is Australia's capital",
            },
            {
              source_quote: "Sydney is Australia's capital",
              claim: "Sydney is Australia's capital",
            },
          ],
        }
      : {
          coverage:
            ++audits === 1
              ? "combined_clauses_need_splitting"
              : "atomic_text_preserved",
          reason: "Both atomic clauses preserved",
        };
  const claims = await engine.extract(text);
  assert.equal(claims.length, 2);
  assert.equal(claims[1].start, text.indexOf("Sydney"));
  assert.equal(audits, 2);
});

test("verbatim coverage cannot drop entities, numbers, negations or conditions", () => {
  for (const [text, quote] of [
    ["A litre contains 500 ml.", "A litre contains"],
    ["Sydney is not the capital.", "Sydney is"],
    ["If heated, water boils.", "water boils"],
  ])
    assert.throws(
      () => checkedVerbatimSpans(text, [{ source_quote: quote }]),
      /cover every/,
    );
  assert.throws(
    () =>
      checkedVerbatimSpans("Canberra is a capital.", [{ source_quote: "Can" }]),
    /cut through/,
  );
});
test("complete quoted compound is still rejected by the structural atomicity gate", async () => {
  const { engine } = fixture();
  const text =
    "Canberra is Australia's capital and Sydney is Australia's capital.";
  engine.model.json = async (_s, _i, schema) =>
    schema.properties.claims
      ? { claims: [{ source_quote: text }] }
      : {
          coverage: "combined_clauses_need_splitting",
          reason: "One item still combines assertions",
        };
  await assert.rejects(engine.extract(text), /incomplete or uncertain/);
});
test("syntax audit obscures factual names, values and predicates while retaining structure", () => {
  const items = obscureContent([
    "Canberra is Australia's capital",
    "Sydney is Australia's capital",
    "A litre contains 500 millilitres and not 1000 millilitres",
  ]);
  assert.equal(items[0], "TERM1 is TERM2 TERM3");
  assert.equal(items[1], "TERM4 is TERM2 TERM3");
  assert.ok(
    !items.join(" ").match(/Canberra|Sydney|Australia|capital|500|1000|litre/),
  );
  assert.match(items[2], /contains .* and not /);
});

test("research handoff preserves unverified input context without truncation", () => {
  const original = "In water, a light wave has a different speed. It may vary.";
  const job = researchSubmissionText("It may vary.", original);
  assert.equal(job.scope, "atomic_claim_with_context");
  assert.ok(job.text.includes(original));
  assert.ok(job.text.includes("It may vary."));
  const long = "x".repeat(4000);
  const bounded = researchSubmissionText("x", long);
  assert.equal(bounded.text, long);
  assert.equal(bounded.scope, "whole_input_with_context");
  assert.deepEqual(researchSubmissionText("A question?", "A question?"), {
    text: "A question?",
    scope: "atomic_claim",
  });
});

test("weak nearest neighbours cannot receive model verdicts", async () => {
  const { engine } = fixture();
  await engine.initialize();
  engine.model.embed = async () => [Array.from({ length: 768 }, (_, i) => i % 2 ? 1 : -1)];
  engine.model.json = async () => { throw new Error("Weak match must not be classified"); };
  const result = await engine.match({ claim: "Unicorns live on Mars.", kind: "assertion" });
  assert.equal(result.status, "not_in_library");
  assert.equal(result.model_assessment, null);
  assert.equal(result.minimum_candidate_similarity, 0.7);
});
test("unverified paragraph and target precede authoritative reviewed evidence", async () => {
  const { engine } = fixture();
  await engine.initialize();
  engine.model.json = async (_system, input) => {
    assert.equal(input.input, "A litre contains 500 millilitres.");
    assert.equal(input.unverified_input_context, "Canberra is Australia's capital. A litre contains 500 millilitres.");
    assert.equal(Object.keys(input).at(-1), "reviewed_fact");
    return { relationship: "contradicts_same_claim", reason: "Reviewed conversion is 1000 millilitres." };
  };
  const result = await engine.match({ claim: "A litre contains 500 millilitres.", kind: "assertion", input_context: "Canberra is Australia's capital. A litre contains 500 millilitres." });
  assert.equal(result.status, "contradicted");
});

import assert from "node:assert/strict";
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

export function validateSemanticReport(
  report,
  { engineRevision, importId, modelConfiguration },
) {
  assert.ok(Array.isArray(report));
  assert.equal(report.length, EVALUATION_CASES.length);
  const ids = report.map((row) => row.id);
  assert.equal(new Set(ids).size, ids.length, "Duplicate case IDs");
  for (const [id, text, expected] of EVALUATION_CASES) {
    const row = report.find((row) => row.id === id);
    assert.ok(row, `Missing case ${id}`);
    assert.equal(row.text, text, `Changed input ${id}`);
    assert.deepEqual(row.expected, expected, `Changed expected labels ${id}`);
    assert.equal(row.pass, true, `Case did not strictly pass ${id}`);
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

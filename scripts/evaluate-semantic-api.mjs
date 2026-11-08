import assert from "node:assert/strict";
import { writeFileSync } from "node:fs";
const origin = process.argv[2] ?? "http://localhost:8081";
const cases = [
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
    details: results.map((r) => ({
      claim: r.claim,
      status: r.status,
      reason: r.reason ?? null,
      inspection: r.inspection ?? null,
      job: r.job ?? null,
      extraction_audit: r.extraction_audit ?? null,
      scope_assessment: r.scope_assessment ?? null,
      assessment: r.model_assessment ?? null,
    })),
  });
  console.log(JSON.stringify(report.at(-1)));
}
if (process.argv[3])
  writeFileSync(process.argv[3], JSON.stringify(report, null, 2) + "\n");
assert.ok(
  report.every((r) => r.pass),
  "Semantic acceptance cases failed",
);

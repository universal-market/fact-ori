import { expect, test } from "vitest";
import { servingAdmissionFixture } from "./fixtures/c013-serving-admission";
import {
  mappedLiteral, protectedLiteral, routeFixtureRequest, type RouteProof,
} from "./fixtures/c013-serving-routing";

const { createTest, internal } = servingAdmissionFixture;
type Fixture = ReturnType<typeof createTest>;
const request = {
  scope: "fixture-client",
  key: "fixture-effect",
  expectedEpoch: 1,
  generation: {
    importId: "same-import", policyId: "fixture-policy", engineId: "fixture-engine",
    indexId: "fixture-index",
  },
  originalText: "Synthetic paragraph",
  effectText: "Synthetic claim",
  publicReview: true,
};

async function setup() {
  const t = createTest();
  const authority = await t.run((ctx) =>
    ctx.db.insert("authority", { name: "serving", epoch: 1, ...request.generation }),
  );
  return { t, authority };
}

function intakeState(t: Fixture) {
  return t.run(async (ctx) => ({
    jobs: await ctx.db.query("jobs").take(10),
    bindings: await ctx.db.query("bindings").take(10),
  }));
}

const empty = { jobs: [], bindings: [] };

function route(t: Fixture, input: unknown, options: {
  preview?: boolean;
  effects?: string[];
  alterProof?: (proof: RouteProof) => RouteProof;
  beforeAdmission?: () => Promise<unknown>;
} = {}) {
  return routeFixtureRequest(input, {
    scope: request.scope, analysisId: "synthetic-analysis", preview: options.preview ?? false,
  }, {
    readGeneration: () => t.query(internal.fixture.generation),
    extract: (text) => (options.effects ?? [text]).map((effect, position) => ({
      position, text: effect,
    })),
    classify: (input) => {
      const proof = { ...input, route: "unmapped" } as const;
      return options.alterProof?.(proof) ?? proof;
    },
    admit: async (args) => {
      await options.beforeAdmission?.();
      return t.mutation(internal.fixture.admission, args);
    },
  });
}

test.each([
  { text: "Literal in preview", preview: true, status: "preview" },
  { text: protectedLiteral, preview: false, status: "withheld" },
  { text: mappedLiteral, preview: false, status: "mapped" },
])("A5: server route $status precedes fallback and admission", async ({ text, preview, status }) => {
  const { t } = await setup();
  expect(await route(t, { text, public_review: true }, {
    preview, alterProof: () => { throw new Error("Unexpected fallback"); },
  })).toEqual({ status });
  expect(await intakeState(t)).toEqual(empty);
});

test("A5: public fields cannot supply authority or invalid consent", async () => {
  const { t } = await setup();
  const text = "Unmapped fixture text";
  for (const input of [{ text, public_review: "true" }, { text, public_review: null },
    { text, public_review: true, epoch: 1 }, { text, public_review: true, route: "unmapped" }]) {
    expect(await route(t, input)).toEqual({ status: "invalid" });
  }
  for (const input of [{ text }, { text, public_review: false }]) {
    expect(await route(t, input)).toEqual({ status: "checked", results: [{ status: "no_consent" }] });
  }
  expect(await intakeState(t)).toEqual(empty);
});

test("A5b: a protected fragment is suppressed without suppressing an unrelated effect", async () => {
  const { t } = await setup();
  const text = `An observation followed by: ${protectedLiteral}`;
  const input = { text, public_review: true };
  expect(await route(t, input, { effects: [protectedLiteral] }))
    .toEqual({ status: "checked", results: [] });
  expect(await intakeState(t)).toEqual(empty);
  const result = await route(t, input, { effects: [protectedLiteral, "Another eligible effect"] });
  const state = await intakeState(t);
  expect(state.jobs).toHaveLength(1);
  expect(state.bindings).toHaveLength(1);
  expect(state.jobs[0].text).toBe("Another eligible effect");
  expect(state.bindings[0]).toMatchObject({
    originalText: text,
    key: JSON.stringify(["synthetic-analysis", 1]),
    jobId: state.jobs[0]._id,
  });
  expect(result).toEqual({ status: "checked", results: [
    { status: "admitted", jobId: state.jobs[0]._id },
  ] });
});

test("A5c: mismatched classification proof fails before any admission", async () => {
  const { t } = await setup();
  const input = { text: "Eligible fixture text", public_review: true };
  const variants: Array<(proof: RouteProof) => RouteProof> = [
    (p) => ({ ...p, generation: { ...p.generation, engineId: "old-engine" } }),
    (p) => ({ ...p, generation: { ...p.generation, indexId: "old-index" } }),
    (p) => ({ ...p, originalText: "Different original" }),
    (p) => ({ ...p, analysisId: "another-analysis" }),
    (p) => ({ ...p, effect: { ...p.effect, text: "Different effect" } }),
    (p) => ({ ...p, effect: { ...p.effect, position: 4 } }),
    (p) => ({ ...p, route: "mapped" }),
  ];
  for (const alterProof of variants) {
    expect(await route(t, input, { alterProof })).toEqual({ status: "unavailable" });
    expect(await intakeState(t)).toEqual(empty);
  }
  expect(await route(t, input, {
    effects: ["First eligible effect", "Second inconsistent effect"],
    alterProof: (proof) => proof.effect.position === 1
      ? { ...proof, analysisId: "another-analysis" } : proof,
  })).toEqual({ status: "unavailable" });
  expect(await intakeState(t)).toEqual(empty);
  const result = await route(t, input);
  const state = await intakeState(t);
  expect(state.bindings).toHaveLength(1);
  expect(state.jobs).toHaveLength(1);
  expect(result).toEqual({ status: "checked", results: [
    { status: "admitted", jobId: state.jobs[0]._id },
  ] });
});

test("A1/A5c: admission rechecks epoch and manifest after classification", async () => {
  for (const patch of [{ epoch: 2 }, { indexId: "incompatible-index" }]) {
    const { t, authority } = await setup();
    const result = await route(t, { text: "Eligible fixture text", public_review: true }, {
      beforeAdmission: () => t.run((ctx) => ctx.db.patch("authority", authority, patch)),
    });
    expect(result).toEqual({ status: "checked", results: [
      { status: "epoch" in patch ? "stale" : "unavailable" },
    ] });
    expect(await intakeState(t)).toEqual(empty);
  }
});

test("A1: same-import epoch advance defeats a captured generation", async () => {
  const { t, authority } = await setup();
  const captured = await t.run((ctx) => ctx.db.get("authority", authority));
  expect(captured?.epoch).toBe(1);
  await t.run((ctx) => ctx.db.patch("authority", authority, { epoch: 2 }));
  const advanced = await t.run((ctx) => ctx.db.get("authority", authority));
  expect(advanced?.importId).toBe(captured?.importId);
  expect(await t.mutation(internal.fixture.admission, request)).toEqual({ status: "stale" });
  expect(await intakeState(t)).toEqual(empty);
});

test("A2: missing authority fails closed for otherwise valid consent", async () => {
  const t = createTest();
  expect(await t.mutation(internal.fixture.admission, request)).toEqual({
    status: "unavailable",
  });
  expect(await intakeState(t)).toEqual(empty);
});

test("A3: concurrent identical attempts share one current job and binding", async () => {
  const { t } = await setup();
  const results = await Promise.all([
    t.mutation(internal.fixture.admission, request),
    t.mutation(internal.fixture.admission, request),
  ]);
  const state = await intakeState(t);
  expect(state.jobs).toHaveLength(1);
  expect(state.bindings).toHaveLength(1);
  expect(state.bindings[0].jobId).toEqual(state.jobs[0]._id);
  expect(results).toEqual(Array(2).fill({ status: "admitted", jobId: state.jobs[0]._id }));
});

test.each([
  { scope: request.scope, epoch: 0, bindingKey: "historical" },
  { scope: "another-client", epoch: 1, bindingKey: "other-scope" },
  {},
  { scope: request.scope, epoch: 1, bindingKey: "unrelated" },
])("A3b: preserves and does not reuse seeded same-text job %j", async (seed) => {
  const { t } = await setup();
  const seededId = await t.run((ctx) =>
    ctx.db.insert("jobs", { text: request.effectText, ...seed }),
  );
  const seededJob = await t.run((ctx) => ctx.db.get("jobs", seededId));
  const result = await t.mutation(internal.fixture.admission, request);
  const state = await intakeState(t);
  expect(state.jobs).toHaveLength(2);
  expect(state.bindings).toHaveLength(1);
  expect(state.bindings[0].jobId).not.toBe(seededId);
  expect(result).toEqual({ status: "admitted", jobId: state.bindings[0].jobId });
  expect(await t.run((ctx) => ctx.db.get("jobs", seededId))).toEqual(seededJob);
});

test("A4: exact payload and consent conflict only while the binding is current", async () => {
  const { t, authority } = await setup();
  await t.mutation(internal.fixture.admission, request);
  const before = await intakeState(t);
  const { publicReview: _, ...absentConsent } = request;
  const variants = [
    { ...request, originalText: request.originalText + " " },
    { ...request, effectText: request.effectText + " " },
    { ...request, publicReview: false },
    absentConsent,
  ];
  for (const variant of variants) {
    expect(await t.mutation(internal.fixture.admission, variant)).toEqual({ status: "conflict" });
  }
  await t.run((ctx) => ctx.db.patch("authority", authority, { epoch: 2 }));
  for (const variant of [...variants, request]) {
    expect(await t.mutation(internal.fixture.admission, { ...variant, expectedEpoch: 2 }))
      .toEqual({ status: "stale" });
  }
  expect(await intakeState(t)).toEqual(before);
});

test.each(["scope", "epoch", "bindingKey", "missing"] as const)(
  "A4b: fails closed without rebinding when linked job has invalid %s",
  async (mismatch) => {
    const { t } = await setup();
    await t.mutation(internal.fixture.admission, request);
    const { jobs: [job] } = await intakeState(t);
    await t.run(async (ctx) => {
      if (mismatch === "missing") await ctx.db.delete("jobs", job._id);
      else if (mismatch === "epoch") await ctx.db.patch("jobs", job._id, { epoch: 2 });
      else await ctx.db.patch("jobs", job._id, { [mismatch]: "different" });
    });
    const before = await intakeState(t);
    expect(await t.mutation(internal.fixture.admission, request)).toEqual({
      status: "unavailable",
    });
    expect(await intakeState(t)).toEqual(before);
  },
);

test("A6: a thrown failure between writes rolls back the job and binding", async () => {
  const { t } = await setup();
  await expect(t.mutation(internal.fixture.admission, { ...request, failAfterJob: true }))
    .rejects.toThrow("Disposable failure before binding insert");
  expect(await intakeState(t)).toEqual(empty);
  expect((await t.mutation(internal.fixture.admission, request)).status).toBe("admitted");
  expect((await intakeState(t)).bindings).toHaveLength(1);
});

async function prepareResult(t: Fixture, kind: "immediate" | "partial") {
  const result = await t.mutation(internal.fixture.admission, request);
  if (result.status !== "admitted") throw new Error("Expected a disposable job");
  return {
    identity: { scope: request.scope, key: "analysis-1", expectedEpoch: 1, kind },
    payload: { answer: "Synthetic answer", evidence: "Synthetic support", jobId: result.jobId },
  };
}

test.each(["immediate", "partial"] as const)(
  "A7a: revocation prevents a fresh %s save and a stale update",
  async (kind) => {
    const { t, authority } = await setup();
    const { identity, payload } = await prepareResult(t, kind);
    expect(await t.mutation(internal.fixture.save, { ...identity, payload }))
      .toEqual({ status: "saved" });
    const historicalResults = await t.run((ctx) => ctx.db.query("results").take(10));
    const historicalIntake = await intakeState(t);
    await t.run((ctx) => ctx.db.patch("authority", authority, { epoch: 2 }));

    expect(await t.mutation(internal.fixture.save, { ...identity, key: "fresh", payload }))
      .toEqual({ status: "stale" });
    expect(await t.mutation(internal.fixture.save, {
      ...identity, payload: { ...payload, answer: "Revoked update" },
    })).toEqual({ status: "stale" });
    expect(await t.run((ctx) => ctx.db.query("results").take(10))).toEqual(historicalResults);
    expect(await intakeState(t)).toEqual(historicalIntake);
  },
);

test.each(["immediate", "partial"] as const)(
  "A7b: projection withholds a previously saved %s payload after revocation",
  async (kind) => {
    const { t, authority } = await setup();
    const { identity, payload } = await prepareResult(t, kind);
    await t.mutation(internal.fixture.save, { ...identity, payload });
    expect(await t.query(internal.fixture.project, identity))
      .toEqual({ status: "current", payload });
    const historicalResults = await t.run((ctx) => ctx.db.query("results").take(10));
    const historicalIntake = await intakeState(t);
    await t.run((ctx) => ctx.db.patch("authority", authority, { epoch: 2 }));

    expect(await t.query(internal.fixture.project, identity)).toEqual({ status: "stale" });
    expect(await t.query(internal.fixture.project, { ...identity, expectedEpoch: 2 }))
      .toEqual({ status: "stale" });
    expect(await t.run((ctx) => ctx.db.query("results").take(10))).toEqual(historicalResults);
    expect(await intakeState(t)).toEqual(historicalIntake);
  },
);

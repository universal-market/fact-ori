import { defineSchema, defineTable, type DataModelFromSchemaDefinition,
  type GenericQueryCtx } from "convex/server";
import { defineTestApp } from "convex-test";
import { v, type Infer } from "convex/values";
import { exactRoute, generationIdentity, matchesGeneration, routeFixtureRequest,
  type RoutingDependencies } from "./c013-serving-routing";

const payload = v.object({
  answer: v.string(),
  evidence: v.string(),
  jobId: v.id("jobs"),
});
const stateKind = v.union(v.literal("immediate"), v.literal("partial"));
const stale = v.object({ status: v.literal("stale") });
const unavailable = v.object({ status: v.literal("unavailable") });

// The fixture has its own schema and no route to a deployed Convex instance.
const schema = defineSchema({
  authority: defineTable({
    name: v.literal("serving"),
    epoch: v.number(),
    importId: v.string(),
    policyId: v.string(),
    engineId: v.string(),
    indexId: v.string(),
  }).index("by_name", ["name"]),
  jobs: defineTable({
    text: v.string(),
    scope: v.optional(v.string()),
    epoch: v.optional(v.number()),
    bindingKey: v.optional(v.string()),
  }),
  bindings: defineTable({
    scope: v.string(),
    key: v.string(),
    epoch: v.number(),
    originalText: v.string(),
    effectText: v.string(),
    jobId: v.id("jobs"),
  }).index("by_scope_and_key", ["scope", "key"]),
  results: defineTable({
    scope: v.string(),
    key: v.string(),
    kind: stateKind,
    epoch: v.number(),
    payload,
  }).index("by_scope_and_key_and_kind", ["scope", "key", "kind"]),
});

const app = defineTestApp({ schema });
type FixtureDb = GenericQueryCtx<DataModelFromSchemaDefinition<typeof schema>>["db"];

function findBinding(db: FixtureDb, scope: string, key: string) {
  return db.query("bindings")
    .withIndex("by_scope_and_key", (q) => q.eq("scope", scope).eq("key", key)).unique();
}

async function eligibleJob(db: FixtureDb, binding: NonNullable<Awaited<ReturnType<typeof findBinding>>>) {
  const job = await db.get("jobs", binding.jobId);
  return job && job.scope === binding.scope && job.epoch === binding.epoch &&
    job.bindingKey === binding.key && job.text === binding.effectText ? job : null;
}

async function resultJobMatches(
  db: FixtureDb, scope: string, key: string, epoch: number, jobId: Infer<typeof payload>["jobId"],
) {
  const binding = await findBinding(db, scope, key);
  return binding?.epoch === epoch && binding.jobId === jobId && !!await eligibleJob(db, binding);
}

const admissionResult = v.union(
  v.object({ status: v.literal("admitted"), jobId: v.id("jobs") }),
  unavailable,
  stale,
  v.object({ status: v.literal("conflict") }),
  v.object({ status: v.literal("no_consent") }),
);
const admission = app.internalMutation({
  args: {
    scope: v.string(),
    key: v.string(),
    expectedEpoch: v.number(),
    generation: generationIdentity,
    originalText: v.string(),
    effectText: v.string(),
    publicReview: v.optional(v.boolean()),
    failAfterJob: v.optional(v.literal(true)),
  },
  returns: admissionResult,
  handler: async (ctx, args): Promise<Infer<typeof admissionResult>> => {
    const authority = await ctx.db.query("authority")
      .withIndex("by_name", (q) => q.eq("name", "serving")).unique();
    if (!authority) return { status: "unavailable" };
    if (authority.epoch !== args.expectedEpoch) return { status: "stale" };
    if (!matchesGeneration(authority, args.generation) ||
        exactRoute(args.originalText) !== "unmapped" ||
        exactRoute(args.effectText) !== "unmapped") {
      return { status: "unavailable" };
    }

    const { scope, key, originalText, effectText, publicReview } = args;
    const existing = await findBinding(ctx.db, scope, key);
    if (existing) {
      if (existing.epoch !== authority.epoch) return { status: "stale" };
      if (existing.originalText !== originalText || existing.effectText !== effectText ||
          publicReview !== true) {
        return { status: "conflict" };
      }
      const job = await eligibleJob(ctx.db, existing);
      if (!job) return { status: "unavailable" };
      return { status: "admitted", jobId: job._id };
    }

    if (publicReview !== true) return { status: "no_consent" };
    const jobId = await ctx.db.insert("jobs", {
      text: effectText, scope, epoch: authority.epoch, bindingKey: key,
    });
    if (args.failAfterJob) throw new Error("Disposable failure before binding insert");
    await ctx.db.insert("bindings", {
      scope, key, epoch: authority.epoch, originalText, effectText, jobId,
    });
    return { status: "admitted", jobId };
  },
});

const resultIdentity = {
  scope: v.string(),
  key: v.string(),
  kind: stateKind,
  expectedEpoch: v.number(),
};
const saveResult = v.union(v.object({ status: v.literal("saved") }), unavailable, stale);
const save = app.internalMutation({
  args: { ...resultIdentity, payload },
  returns: saveResult,
  handler: async (ctx, args): Promise<Infer<typeof saveResult>> => {
    const authority = await ctx.db.query("authority")
      .withIndex("by_name", (q) => q.eq("name", "serving")).unique();
    if (!authority) return { status: "unavailable" };
    if (authority.epoch !== args.expectedEpoch) return { status: "stale" };
    const { scope, key, kind } = args;
    const prior = await ctx.db.query("results").withIndex("by_scope_and_key_and_kind",
      (q) => q.eq("scope", scope).eq("key", key).eq("kind", kind)).unique();
    if (prior && prior.epoch !== authority.epoch) return { status: "stale" };

    if (!await resultJobMatches(ctx.db, scope, key, authority.epoch, args.payload.jobId)) {
      return { status: "unavailable" };
    }
    if (prior) await ctx.db.patch("results", prior._id, { payload: args.payload });
    else await ctx.db.insert("results", {
      scope, key, kind, epoch: authority.epoch, payload: args.payload,
    });
    return { status: "saved" };
  },
});

const projection = v.union(
  v.object({ status: v.literal("current"), payload }),
  v.object({ status: v.literal("missing") }),
  unavailable,
  stale,
);
const project = app.internalQuery({
  args: resultIdentity,
  returns: projection,
  handler: async (ctx, args): Promise<Infer<typeof projection>> => {
    const authority = await ctx.db.query("authority")
      .withIndex("by_name", (q) => q.eq("name", "serving")).unique();
    if (!authority) return { status: "unavailable" };
    if (authority.epoch !== args.expectedEpoch) return { status: "stale" };
    const result = await ctx.db.query("results").withIndex("by_scope_and_key_and_kind",
      (q) => q.eq("scope", args.scope).eq("key", args.key).eq("kind", args.kind)).unique();
    if (!result) return { status: "missing" };
    if (result.epoch !== authority.epoch) return { status: "stale" };
    if (!await resultJobMatches(ctx.db, args.scope, args.key, result.epoch, result.payload.jobId)) {
      return { status: "unavailable" };
    }
    return { status: "current", payload: result.payload };
  },
});

const generation = app.internalQuery({
  args: {},
  returns: v.union(v.null(), v.object({ epoch: v.number(), ...generationIdentity.fields })),
  handler: async (ctx) => {
    const row = await ctx.db.query("authority")
      .withIndex("by_name", (q) => q.eq("name", "serving")).unique();
    if (!row) return null;
    const { epoch, importId, policyId, engineId, indexId } = row;
    return { epoch, importId, policyId, engineId, indexId };
  },
});

export const servingAdmissionFixture = app.defineModules({
  fixture: { admission, save, project, generation },
});

type FixtureClient = Pick<ReturnType<typeof servingAdmissionFixture.createTest>, "mutation" | "query">;

export function serveFixtureResults(
  client: FixtureClient,
  input: unknown,
  context: Parameters<typeof routeFixtureRequest>[1],
  kind: Infer<typeof stateKind>,
  result: Pick<Infer<typeof payload>, "answer" | "evidence">,
  routing: RoutingDependencies,
  barriers: { beforeSave?: () => Promise<unknown>; beforeProject?: () => Promise<unknown> } = {},
) {
  const { fixture } = servingAdmissionFixture.internal;
  return routeFixtureRequest(input, context, {
    ...routing,
    admit: async (request) => {
      const admitted = await client.mutation(fixture.admission, request);
      if (admitted.status !== "admitted") return admitted;
      // The admission key encodes the trusted analysis ID and effect position.
      const identity = { scope: request.scope, key: request.key,
        expectedEpoch: request.expectedEpoch, kind };
      await barriers.beforeSave?.();
      const saved = await client.mutation(fixture.save, {
        ...identity, payload: { ...result, jobId: admitted.jobId },
      });
      if (saved.status !== "saved") return saved;
      await barriers.beforeProject?.();
      return client.query(fixture.project, identity);
    },
  });
}

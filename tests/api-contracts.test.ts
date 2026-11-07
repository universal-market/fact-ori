/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import { describe, expect, test } from "vitest";
import schema from "../convex/schema";
import { internal } from "../convex/_generated/api";

const modules = import.meta.glob("../convex/**/*.{ts,js}");
const postId = "1d4e6038-3d1f-4ba6-ab60-90b42bb33607";

async function setup() {
  const t = convexTest(schema, modules);
  await t.run(async (ctx) => {
    await ctx.db.insert("library", { name: "current", importId: "test-import", importedAt: 1000, claimCount: 2 });
    for (const [claimId, text, state] of [["C900", "Known answer", "approved"],
      ["C901", "Withheld answer", "pending"]] as const) {
      await ctx.db.insert("claims", { claimId, version: 1, recordHash: "0".repeat(64), state,
        normalizedClaim: text.toLowerCase(), searchText: text, importId: "test-import",
        evidencePackage: { answer_kind: "supported_assertion", evidence_verdict: "supported", answer: text },
        sourceReviews: [] });
    }
    await ctx.db.insert("aliases", { normalizedText: "clarify", kind: "clarify",
      clarification: "Which scope?", importId: "test-import" });
  });
  return t;
}

type TestInstance = Awaited<ReturnType<typeof setup>>;
async function check(t: TestInstance, text: string, publicReview: boolean, key: string) {
  const response = await t.fetch("/v1/check", { method: "POST", headers: {
    "Content-Type": "application/json", "Idempotency-Key": key,
  }, body: JSON.stringify({ text, public_review: publicReview }) });
  return { code: response.status, body: await response.json() };
}

describe("queue-only request-key scope", () => {
  for (const [text, expected] of [["Uncovered private A", "not_in_library"],
    ["Known answer", "answer"], ["Clarify", "needs_clarification"],
    ["Withheld answer", "withheld"]]) {
    for (const consent of [false, true]) {
      if (consent && expected === "not_in_library") continue;
      test(`${expected} with public_review=${consent} ignores keys and stores no submission`, async () => {
        const t = await setup();
        const first = await check(t, text, consent, "shared-key");
        expect(first.code).toBe(200);
        expect(first.body.status).toBe(expected);
        expect(await t.run((ctx) => ctx.db.query("requestKeys").take(5))).toEqual([]);
        expect(await t.run((ctx) => ctx.db.query("jobs").take(5))).toEqual([]);
        const queued = await check(t, "Different public request", true, "shared-key");
        expect(queued.code).toBe(202);
        // A key already reserved by public work is still ignored on these paths.
        const again = await check(t, text, consent, "shared-key");
        expect(again.code).toBe(200);
        expect(again.body.status).toBe(expected);
      });
    }
  }
  test("public queue retries deduplicate, conflicting text fails, opt-out stays read-only", async () => {
    const t = await setup();
    const first = await check(t, "New public request", true, "queue-key");
    const retry = await check(t, "  NEW public request?  ", true, "queue-key");
    expect(first.code).toBe(202);
    expect(retry.body.job.id).toBe(first.body.job.id);
    expect((await check(t, "Changed public request", true, "queue-key")).code).toBe(409);
    expect((await check(t, "Changed private request", false, "queue-key")).code).toBe(200);
    expect(await t.run((ctx) => ctx.db.query("jobs").take(5))).toHaveLength(1);
    expect(await t.run((ctx) => ctx.db.query("requestKeys").take(5))).toHaveLength(1);
  });
});

describe("linked research progress", () => {
  async function linked() {
    const t = await setup();
    const id = await t.run((ctx) => ctx.db.insert("jobs", {
      text: "Public research", normalizedText: "public research", status: "in_progress",
      createdAt: 1000, updatedAt: 1000, tiloriPostId: postId, leaseUntil: 0,
    }));
    return { t, id };
  }
  test("completed existing work and later blocked/canceled/reopened revisions reconcile", async () => {
    const { t, id } = await linked();
    let updatedAt = 1000;
    for (const [index, status] of (["done", "blocked", "canceled", "in_progress"] as const).entries()) {
      const result = await t.mutation(internal.checks.reconcileJob, { id, postId,
        postRevision: index + 1, observedAt: 2000 + index, status,
        expectedUpdatedAt: updatedAt, recorder: "@adrian.factomaton" });
      expect(result.updatedAt).toBeGreaterThan(updatedAt);
      updatedAt = result.updatedAt;
      const job = await t.query(internal.checks.getJob, { id });
      if (!job) throw new Error("Linked job missing");
      expect(job.status).toBe(status);
      expect(job.progress_source).toBe("tilori_post");
      expect(job.post_revision).toBe(index + 1);
      expect(job.progress_recorded_by).toBe("@adrian.factomaton");
      expect(job).not.toHaveProperty("verdict");
    }
  });
  test("exact retry is idempotent and stale or mismatched updates fail without writes", async () => {
    const { t, id } = await linked();
    const args = { id, postId, postRevision: 3, observedAt: 3000, status: "done" as const,
      expectedUpdatedAt: 1000, recorder: "@adrian.factomaton" };
    const first = await t.mutation(internal.checks.reconcileJob, args);
    expect(await t.mutation(internal.checks.reconcileJob, args)).toEqual(first);
    const before = await t.query(internal.checks.getJob, { id });
    const changes = [
      { postId: "00000000-0000-4000-8000-000000000000" },
      { postRevision: 4, observedAt: 4000, status: "blocked" },
      { expectedUpdatedAt: first.updatedAt, postRevision: 2, observedAt: 4000 },
      { expectedUpdatedAt: first.updatedAt, postRevision: 4, observedAt: 2999 },
      { expectedUpdatedAt: first.updatedAt, observedAt: 4000, status: "blocked" },
      { expectedUpdatedAt: first.updatedAt, postRevision: 4, observedAt: Date.now() + 60000 },
      { expectedUpdatedAt: first.updatedAt, postRevision: 0, observedAt: 4000 },
      { expectedUpdatedAt: first.updatedAt, postRevision: 4, observedAt: 4000, recorder: "" },
    ];
    for (const change of changes) {
      await expect(t.mutation(internal.checks.reconcileJob, { ...args, ...change } as typeof args)).rejects.toThrow();
      expect(await t.query(internal.checks.getJob, { id })).toEqual(before);
    }
  });
  test("legacy handoff stays explicit and unlinked jobs cannot reconcile", async () => {
    const { t, id } = await linked();
    const job = await t.query(internal.checks.getJob, { id });
    if (!job) throw new Error("Linked job missing");
    expect(job.progress_source).toBe("operator_handoff");
    await t.run((ctx) => ctx.db.patch(id, { tiloriPostId: undefined }));
    await expect(t.mutation(internal.checks.reconcileJob, { id, postId, postRevision: 1,
      status: "done", observedAt: 2000, expectedUpdatedAt: 1000, recorder: "@adrian.factomaton" })).rejects.toThrow();
  });
  test("linked queued progress is discoverable for reconciliation and excluded from dispatch", async () => {
    const { t, id } = await linked();
    await t.mutation(internal.checks.reconcileJob, { id, postId, postRevision: 1,
      status: "not_started", observedAt: 2000, expectedUpdatedAt: 1000, recorder: "@adrian.factomaton" });
    expect(await t.query(internal.checks.listQueued, { now: Date.now() })).toEqual([]);
    const page = await t.query(internal.checks.listForReconciliation, { status: "not_started",
      paginationOpts: { numItems: 1, cursor: null } });
    expect(page.page).toHaveLength(1);
    expect(page.page[0]._id).toBe(id);
    expect(await t.mutation(internal.checks.claimJob, { id, worker: "second-worker" })).toBeNull();
  });
});

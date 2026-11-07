/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import { describe, expect, test } from "vitest";
import schema from "../convex/schema";
import { withImplementationProvenance } from "../convex/provenance";

const modules = import.meta.glob("../convex/**/*.{ts,js}");
const hash = "0".repeat(64);

async function setup() {
  const t = convexTest(schema, modules);
  await t.run(async (ctx) => {
    await ctx.db.insert("library", { name: "current", importId: "fixture", importedAt: 1, claimCount: 3 });
    for (const [claimId, text, kind, state] of [
      ["C900", "Known", "supported_assertion", "approved"],
      ["C901", "Abstain", "reviewed_abstention", "approved"],
      ["C902", "Withheld", "supported_assertion", "pending"],
    ] as const) {
      await ctx.db.insert("claims", { claimId, normalizedClaim: text.toLowerCase(), searchText: text,
        version: 1, recordHash: hash, state, importId: "fixture",
        evidencePackage: { answer_kind: kind, evidence_verdict: kind === "reviewed_abstention" ? "insufficient_evidence" : "supported", answer: text },
        sourceReviews: [] });
      await ctx.db.insert("recordVersions", { claimId, version: 1, recordHash: hash,
        canonicalRecord: JSON.stringify({ id: claimId, version: 1, claim: text }) });
    }
    await ctx.db.insert("aliases", { normalizedText: "clarify", kind: "clarify",
      clarification: "Which scope?", importId: "fixture" });
  });
  return t;
}

async function expectPending(response: Response, code: number) {
  expect(response.status).toBe(code);
  expect(response.headers.get("cache-control")).toBe("no-store");
  const body = await response.json();
  expect(body.implementation_review).toBe("pending");
  expect(body.implementation_provenance).toMatchObject({ schema_version: 1,
    binding_state: "unconfigured", source: null, build: null, review_receipts: [],
    historical_receipts_loaded: false });
  return body;
}

const request = (text: string, public_review = false, key?: string) => ({ method: "POST", headers: {
  "Content-Type": "application/json", ...(key ? { "Idempotency-Key": key } : {}),
}, body: JSON.stringify({ text, public_review }) });

describe("unconfigured runtime provenance on registered JSON responses", () => {
  test.each([["Known", "answer"], ["Abstain", "abstain"], ["Withheld", "withheld"],
    ["Clarify", "needs_clarification"], ["Unknown", "not_in_library"]])("%s preserves evidence semantics", async (text, status) => {
    const t = await setup();
    const body = await expectPending(await t.fetch("/v1/check", request(text)), 200);
    expect(body.status).toBe(status);
    if (status === "answer") expect(body.verdict).toBe("supported");
    if (status === "abstain") expect(body.verdict).toBe("insufficient_evidence");
    if (status === "not_in_library") expect(body.answer).toBeNull();
  });

  test("health, records, jobs and missing/withheld responses use the same envelope", async () => {
    const t = await setup();
    await expectPending(await t.fetch("/health"), 200);
    const queued = await expectPending(await t.fetch("/v1/check", request("New public", true, "one")), 202);
    await expectPending(await t.fetch(`/v1/jobs/${queued.job.id}`), 200);
    await expectPending(await t.fetch("/v1/jobs/invalid"), 404);
    const record = await expectPending(await t.fetch(`/v1/records/C900?version=1&sha256=${hash}`), 200);
    expect(record.frozen_record.claim).toBe("Known");
    await expectPending(await t.fetch(`/v1/records/C999?version=1&sha256=${hash}`), 404);
    await expectPending(await t.fetch(`/v1/records/C902?version=1&sha256=${hash}`), 409);
  });

  test("unseeded, idempotency conflict and queue-full results stay pending", async () => {
    const empty = convexTest(schema, modules);
    await expectPending(await empty.fetch("/health"), 200);
    await expectPending(await empty.fetch("/v1/check", request("Unknown")), 503);
    const t = await setup();
    await t.fetch("/v1/check", request("First", true, "shared"));
    await expectPending(await t.fetch("/v1/check", request("Second", true, "shared")), 409);
    await t.run(async (ctx) => {
      for (let i = 0; i < 499; i++) await ctx.db.insert("jobs", { text: `q${i}`, normalizedText: `q${i}`,
        status: "not_started", createdAt: 1, updatedAt: 1 });
    });
    const full = await expectPending(await t.fetch("/v1/check", request("Beyond cap", true)), 503);
    expect(full.status).toBe("queue_full");
  });

  test("validation errors disclose pending and submitted provenance cannot promote it", async () => {
    const t = await setup();
    for (const [init, code] of [
      [{ method: "POST", body: "text" }, 415],
      [{ method: "POST", headers: { "Content-Type": "application/json" }, body: "{" }, 400],
      [{ method: "POST", headers: { "Content-Type": "application/json" }, body: "x".repeat(12001) }, 413],
      [{ ...request("Known"), body: JSON.stringify({ text: "Known", implementation_review: "accepted" }) }, 400],
      [{ ...request("Known"), headers: { "Content-Type": "application/json", "Idempotency-Key": " " } }, 400],
    ] as const) await expectPending(await t.fetch("/v1/check", init), code);
    await expectPending(await t.fetch("/v1/records/C900"), 400);
    expect(withImplementationProvenance({ implementation_review: "accepted",
      implementation_provenance: { binding_state: "accepted" } }).implementation_review).toBe("pending");
    expect(withImplementationProvenance({ implementation_provenance: "forged" })
      .implementation_provenance.binding_state).toBe("unconfigured");
    const options = await t.fetch("/v1/check", { method: "OPTIONS" });
    expect(options.status).toBe(204);
    expect(await options.text()).toBe("");
  });

  test("handled backend failures carry the envelope without exposing internals", async () => {
    const t = await setup();
    await t.run(async (ctx) => {
      const claim = await ctx.db.query("claims").withIndex("by_claimId", q => q.eq("claimId", "C900")).unique();
      await ctx.db.patch(claim!._id, { evidencePackage: null });
    });
    const failed = await expectPending(await t.fetch("/v1/check", request("Known")), 503);
    expect(failed.error).toBe("Library check unavailable");
    await t.run(async (ctx) => {
      const row = await ctx.db.query("recordVersions").withIndex("by_claimId_and_version", q =>
        q.eq("claimId", "C900").eq("version", 1)).unique();
      await ctx.db.patch(row!._id, { canonicalRecord: "invalid JSON" });
    });
    const inspected = await expectPending(await t.fetch(`/v1/records/C900?version=1&sha256=${hash}`), 503);
    expect(inspected.error).toBe("Record inspection unavailable");
  });
});

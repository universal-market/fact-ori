/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import { afterEach, expect, test, vi } from "vitest";
import schema from "../convex/schema";

const modules = import.meta.glob("../convex/**/*.{ts,js}");
afterEach(() => vi.unstubAllEnvs());

function request(public_review?: boolean) {
  return { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": "launch" },
    body: JSON.stringify({ text: "An uncovered question", ...(public_review === undefined ? {} : { public_review }) }) };
}

test("read-only launch rejects intake without persisting text or keys, while checks work", async () => {
  vi.stubEnv("FACT_ORI_PUBLIC_READ_ONLY", "true");
  const t = convexTest(schema, modules);
  await t.run(ctx => ctx.db.insert("library", { name: "current", importId: "fixture", importedAt: 1, claimCount: 0 }));
  const response = await t.fetch("/v1/check", request(true));
  expect(response.status).toBe(403);
  const body = await response.json();
  expect(body.error).toBe("Public research intake is disabled on this deployment.");
  expect(body.implementation_review).toBe("pending");
  for (const consent of [false, undefined]) {
    const read = await t.fetch("/v1/check", request(consent));
    expect(read.status).toBe(200);
    expect((await read.json()).status).toBe("not_in_library");
  }
  expect(await t.run(ctx => ctx.db.query("jobs").take(1))).toEqual([]);
  expect(await t.run(ctx => ctx.db.query("requestKeys").take(1))).toEqual([]);
});

test("local intake remains opt-in when read-only launch is not enabled", async () => {
  vi.stubEnv("FACT_ORI_PUBLIC_READ_ONLY", "false");
  const t = convexTest(schema, modules);
  await t.run(ctx => ctx.db.insert("library", { name: "current", importId: "fixture", importedAt: 1, claimCount: 0 }));
  expect((await t.fetch("/v1/check", request(true))).status).toBe(202);
  expect(await t.run(ctx => ctx.db.query("jobs").take(2))).toHaveLength(1);
});

/// <reference types="vite/client" />
// Diagnostic only: synthetic states below are never real curation decisions.
import { convexTest } from "convex-test";
import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { python } from "../scripts/python.mjs";
import schema from "../convex/schema";
import { internal } from "../convex/_generated/api";
import { normalize } from "../convex/contract";

const modules = import.meta.glob("../convex/**/*.{ts,js}");
const json = (path: string) => JSON.parse(readFileSync(path, "utf8"));
const fix = "scripts/fixtures/c007a-v3/";
const offline = json(fix + "pending-consumer-results-v1.json");
const pending = json(fix + "pending-view-v1.json");
const record = json(fix + "record.json");
const review = json(fix + "source-review.json");
const catalog = json(fix + "predicate-catalog-v1.json");
const canonicalRecord = execFileSync(python(), ["-B", "-c",
  "import json;print(json.dumps(json.load(open('scripts/fixtures/c007a-v3/record.json')),sort_keys=True,separators=(',',':')),end='')"],
  { encoding: "utf8" });
const hash = catalog.candidate_binding.record_digest;

function bridge(state: "pending" | "approved") {
  const pkg = structuredClone(pending.claims[0]);
  pkg.state = state;
  // Deliberate in-memory bypass for diagnosis, NOT an accepted adapter or event.
  if (state === "approved") {
    pkg.answer_kind = "supported_assertion";
    pkg.answer = record.answer;
  }
  return { importId: "e".repeat(64),
    versions: [{ claimId: "C007a", version: 3, recordHash: hash, canonicalRecord }],
    claims: [{ claimId: "C007a", version: 3, recordHash: hash, state,
      evidencePackage: pkg, sourceReviews: [review] }],
    aliases: catalog.routes.slice(0, 3).map((r: { query: string }) => ({
      text: r.query, kind: "claim" as const, claimId: "C007a", version: 3, recordHash: hash,
    })),
  };
}

describe("C007a actual runtime compatibility evaluation (isolated)", () => {
  test("offline seed is not a valid active import and rejection leaves database empty", async () => {
    const t = convexTest(schema, modules);
    await expect(t.mutation(internal.library.importSnapshot, offline.seed)).rejects.toThrow();
    const rows = await t.run(async (ctx) => ({
      library: await ctx.db.query("library").collect(), claims: await ctx.db.query("claims").collect(),
      versions: await ctx.db.query("recordVersions").collect(), aliases: await ctx.db.query("aliases").collect(),
    }));
    expect(rows).toEqual({ library: [], claims: [], versions: [], aliases: [] });
  });

  test("forced legacy pending bridge withholds all three predicates and inspection", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(internal.library.importSnapshot, bridge("pending"));
    for (const r of catalog.routes.slice(0, 3)) {
      const result = await t.mutation(internal.checks.check, { text: r.query, publicReview: false });
      expect(result.status).toBe("withheld"); expect(result.answer).toBeNull();
    }
    const result = await t.query(internal.library.inspect, { claimId: "C007a", version: 3, recordHash: hash });
    expect(result.status).toBe("withheld");
    expect(result).not.toHaveProperty("source_reviews");
  });

  test("current alias storage normalizes literals and cannot represent Q4 matching policy", () => {
    for (const r of catalog.routes.slice(0, 3)) {
      expect(normalize(r.query)).toBe(normalize(r.query.toUpperCase() + "  "));
      expect(normalize(r.query)).toBe(normalize(r.query.replaceAll(" ", "  ")));
    }
  });

  test("deliberately bypassed approval returns compound answer for every predicate and changed literal", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(internal.library.importSnapshot, bridge("approved"));
    for (const r of catalog.routes.slice(0, 3)) {
      for (const text of [r.query, r.query.toUpperCase() + "  "]) {
        const result = await t.mutation(internal.checks.check, { text, publicReview: false });
        expect(result.status).toBe("answer");
        expect(result.answer).toBe(record.answer);
        expect(result.answer).not.toBe(r.proposed_answer);
      }
    }
  });
});

/// <reference types="vite/client" />
import { convexTest } from "convex-test";
import { describe, expect, test } from "vitest";
import { execFileSync } from "node:child_process";
import schema from "../convex/schema";
import { internal } from "../convex/_generated/api";

const modules = import.meta.glob("../convex/**/*.{ts,js}");
type Spec = { id: string; text: string; state?: "approved" | "pending" };
type Alias = { text: string; target?: string; clarification?: string };

async function snapshot(specs: Spec[], aliases: Alias[] = [], importId = "a".repeat(64)) {
  const versions = await Promise.all(specs.map(async ({ id, text }) => {
    const canonicalRecord = JSON.stringify({ id, version: 1, claim: text, scope: `Scope of ${id}` });
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalRecord));
    const recordHash = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
    return { claimId: id, version: 1, canonicalRecord, recordHash };
  }));
  return { importId, versions,
    claims: specs.map(({ id, text, state = "approved" }) => {
      const version = versions.find((v) => v.claimId === id)!;
      return { claimId: id, version: 1, recordHash: version.recordHash, state,
        evidencePackage: { claim_id: id, selected_version: 1, state,
          history: [{ version: 1, record_sha256: version.recordHash }],
          claim_under_review: text, answer_kind: "supported_assertion", answer: `Answer for ${id}`,
          evidence_verdict: "supported" }, sourceReviews: [] };
    }),
    aliases: aliases.map(({ text, target, clarification }) => {
      if (!target) return { text, kind: "clarify" as const, clarification: clarification ?? "Which scope?" };
      const version = versions.find((v) => v.claimId === target)!;
      return { text, kind: "claim" as const, claimId: target, version: 1, recordHash: version.recordHash };
    }),
  };
}

function backend() { return convexTest(schema, modules); }
type T = ReturnType<typeof backend>;
async function query(t: T, text: string) {
  return await t.mutation(internal.checks.check, { text, publicReview: false });
}
async function database(t: T) {
  return await t.run(async (ctx) => ({
    library: await ctx.db.query("library").collect(),
    claims: await ctx.db.query("claims").collect(),
    aliases: await ctx.db.query("aliases").collect(),
    versions: await ctx.db.query("recordVersions").collect(),
  }));
}

describe("snapshot alias/canonical scope boundaries", () => {
  for (const state of ["approved", "pending"] as const) {
    test(`rejects an X alias shadowing ${state} Y canonical wording, atomically`, async () => {
      const t = convexTest(schema, modules);
      await t.mutation(internal.library.importSnapshot, await snapshot([
        { id: "OLD", text: "Previous active claim" },
      ], [{ text: "Previous alias", target: "OLD" }]));
      const before = await database(t);
      const incoming = await snapshot([
        { id: "X", text: "Certified election result" },
        { id: "Y", text: "Ballot validity", state },
      ], [{ text: "Fresh alias before the collision", target: "X" },
        { text: "  BALLOT   validity??? ", target: "X" }], "b".repeat(64));
      await expect(t.mutation(internal.library.importSnapshot, incoming))
        .rejects.toThrow("Alias conflicts with canonical claim wording");
      expect(await database(t)).toEqual(before);
      expect((await query(t, "Previous alias")).answer).toBe("Answer for OLD");
      expect((await query(t, "Ballot validity")).answer).toBeNull();
    });
  }
  test("allows a same-claim alias under existing case/whitespace/question normalization", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(internal.library.importSnapshot, await snapshot([
      { id: "X", text: "One litre equals 1000 millilitres" },
    ], [{ text: " ONE litre  equals 1000 MILLILITRES??? ", target: "X" }]));
    const answer = await query(t, "One litre equals 1000 millilitres");
    if (!("matching" in answer) || !("evidence_package" in answer)) throw new Error("Expected scoped answer");
    expect(answer.status).toBe("answer");
    expect(answer.matching).toBe("reviewed_exact_alias");
    expect(answer.evidence_package.claim_id).toBe("X");
  });
  test("rejects clarification shadowing canonical wording", async () => {
    const t = convexTest(schema, modules);
    await expect(t.mutation(internal.library.importSnapshot, await snapshot([
      { id: "X", text: "Canonical claim" },
    ], [{ text: "Canonical claim?", clarification: "Which claim?" }])))
      .rejects.toThrow("Alias conflicts with canonical claim wording");
    expect((await database(t)).library).toEqual([]);
  });
  test("same wording on two claims stays ambiguous and cannot be overridden by an alias", async () => {
    const t = convexTest(schema, modules);
    const specs = [{ id: "X", text: "Shared wording" }, { id: "Y", text: "Shared wording" }];
    await t.mutation(internal.library.importSnapshot, await snapshot(specs));
    expect((await query(t, "Shared wording")).status).toBe("needs_clarification");
    const before = await database(t);
    await expect(t.mutation(internal.library.importSnapshot, await snapshot(specs,
      [{ text: "Shared wording", target: "X" }], "b".repeat(64))))
      .rejects.toThrow("Alias conflicts with canonical claim wording");
    expect(await database(t)).toEqual(before);
  });
  test("a retained inactive canonical row does not block an incoming alias", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(internal.library.importSnapshot, await snapshot([
      { id: "OLD", text: "Retained old wording" },
    ]));
    await t.mutation(internal.library.importSnapshot, await snapshot([
      { id: "NEW", text: "New scoped claim" },
    ], [{ text: "Retained old wording", target: "NEW" }], "b".repeat(64)));
    const answer = await query(t, "Retained old wording");
    if (!("evidence_package" in answer)) throw new Error("Expected scoped answer");
    expect(answer.evidence_package.claim_id).toBe("NEW");
    expect((await database(t)).claims).toHaveLength(2);
  });
  test("an inactive old alias cannot shadow an incoming canonical claim", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(internal.library.importSnapshot, await snapshot([
      { id: "OLD", text: "Old scoped claim" },
    ], [{ text: "New scoped claim", target: "OLD" }]));
    await t.mutation(internal.library.importSnapshot, await snapshot([
      { id: "NEW", text: "New scoped claim" },
    ], [], "b".repeat(64)));
    const answer = await query(t, "New scoped claim");
    if (!("matching" in answer) || !("evidence_package" in answer)) throw new Error("Expected scoped answer");
    expect(answer.matching).toBe("exact_record_claim");
    expect(answer.evidence_package.claim_id).toBe("NEW");
  });
  test("current exported seed imports and retries without changing selected answers", async () => {
    // Export uses the actual immutable records, reviewed catalog and curation projection.
    const seed = JSON.parse(execFileSync("python", ["-B", "scripts/export_api_seed.py"], { encoding: "utf8" }));
    const t = convexTest(schema, modules);
    const result = await t.mutation(internal.library.importSnapshot, seed);
    expect(result.claims).toBe(5);
    expect(result.versions).toBe(7);
    expect(await t.mutation(internal.library.importSnapshot, seed)).toEqual(result);
    for (const alias of seed.aliases) {
      const answer = await query(t, alias.text);
      if (alias.kind === "clarify") expect(answer.status).toBe("needs_clarification");
      else {
        if (!("evidence_package" in answer) || !("inspection" in answer)) throw new Error("Expected pinned answer");
        expect(answer.evidence_package.claim_id).toBe(alias.claimId);
        expect(answer.inspection.version).toBe(alias.version);
        expect(answer.inspection.sha256).toBe(alias.recordHash);
      }
    }
    const unknown = await query(t, "Unverified distant scope");
    expect(unknown.answer).toBeNull();
    expect(unknown.status).toBe("not_in_library");
    if (!("candidates" in unknown)) throw new Error("Expected candidate-only response");
    expect(unknown.candidates.every((c: { scope_match_established: boolean }) => c.scope_match_established === false)).toBe(true);
  });
});

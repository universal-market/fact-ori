import { v } from "convex/values";
import { internalMutation, internalQuery } from "./_generated/server";
import { isDigest, normalize } from "./contract";
import { publicationState } from "./schema";

const versionInput = v.object({
  claimId: v.string(), version: v.number(), recordHash: v.string(), canonicalRecord: v.string(),
});
const claimInput = v.object({
  claimId: v.string(), version: v.number(), recordHash: v.string(), state: publicationState,
  evidencePackage: v.any(), sourceReviews: v.any(),
});
const aliasInput = v.object({
  text: v.string(), kind: v.union(v.literal("claim"), v.literal("clarify")),
  claimId: v.optional(v.string()), version: v.optional(v.number()),
  recordHash: v.optional(v.string()), clarification: v.optional(v.string()),
});

export const importSnapshot = internalMutation({
  args: { importId: v.string(), versions: v.array(versionInput), claims: v.array(claimInput), aliases: v.array(aliasInput) },
  returns: v.object({ importId: v.string(), claims: v.number(), versions: v.number() }),
  handler: async (ctx, args) => {
    if (!isDigest(args.importId) || args.versions.length > 100 || args.claims.length > 100 || args.aliases.length > 500) {
      throw new Error("Invalid or oversized library snapshot");
    }
    const versionKeys = new Set<string>();
    for (const row of args.versions) {
      const key = `${row.claimId}/${row.version}`;
      const record = JSON.parse(row.canonicalRecord);
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(row.canonicalRecord));
      const hash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
      if (versionKeys.has(key) || !Number.isSafeInteger(row.version) || row.version < 1 ||
          hash !== row.recordHash || record.id !== row.claimId || record.version !== row.version) {
        throw new Error("Frozen record binding mismatch");
      }
      versionKeys.add(key);
      const prior = await ctx.db.query("recordVersions").withIndex("by_claimId_and_version", (q) =>
        q.eq("claimId", row.claimId).eq("version", row.version)).unique();
      if (prior && (prior.recordHash !== row.recordHash || prior.canonicalRecord !== row.canonicalRecord)) {
        throw new Error("Immutable record version already exists with different bytes");
      }
      if (!prior) await ctx.db.insert("recordVersions", row);
    }
    const claimIds = new Set<string>();
    const canonicalTargets = new Map<string, Set<string>>();
    for (const row of args.claims) {
      const record = await ctx.db.query("recordVersions").withIndex("by_claimId_and_version", (q) =>
        q.eq("claimId", row.claimId).eq("version", row.version)).unique();
      const selected = row.evidencePackage;
      const history = selected.history?.find((item: { version: number }) => item.version === row.version);
      if (claimIds.has(row.claimId) || !record || record.recordHash !== row.recordHash ||
          selected.claim_id !== row.claimId || selected.selected_version !== row.version ||
          selected.state !== row.state || history?.record_sha256 !== row.recordHash) {
        throw new Error("Current projection binding mismatch");
      }
      claimIds.add(row.claimId);
      const prior = await ctx.db.query("claims").withIndex("by_claimId", (q) => q.eq("claimId", row.claimId)).unique();
      if (prior && prior.version > row.version) throw new Error("Refusing a record-version rollback");
      const frozen = JSON.parse(record.canonicalRecord);
      const normalizedClaim = normalize(frozen.claim);
      const targets = canonicalTargets.get(normalizedClaim) ?? new Set<string>();
      targets.add(row.claimId);
      canonicalTargets.set(normalizedClaim, targets);
      const value = { ...row, normalizedClaim,
        searchText: `${frozen.claim} ${frozen.scope}`, importId: args.importId };
      if (prior) await ctx.db.replace(prior._id, value);
      else await ctx.db.insert("claims", value);
    }
    const aliasKeys = new Set<string>();
    for (const { text, ...row } of args.aliases) {
      const normalizedText = normalize(text);
      if (!normalizedText || aliasKeys.has(normalizedText)) throw new Error("Duplicate or blank alias");
      aliasKeys.add(normalizedText);
      if (row.kind === "claim") {
        const claim = args.claims.find((item) => item.claimId === row.claimId);
        if (!claim || claim.version !== row.version || claim.recordHash !== row.recordHash) {
          throw new Error("Alias needs exact current version and digest");
        }
      } else if (!row.clarification) throw new Error("Clarification text required");
      // Only this incoming snapshot is active after commit. An alias may repeat
      // its own canonical wording, but must not shadow another scoped claim.
      const targets = canonicalTargets.get(normalizedText);
      if (targets && (row.kind !== "claim" || targets.size !== 1 || !targets.has(row.claimId!))) {
        throw new Error("Alias conflicts with canonical claim wording");
      }
      const prior = await ctx.db.query("aliases").withIndex("by_normalizedText", (q) => q.eq("normalizedText", normalizedText)).unique();
      const value = { ...row, normalizedText, importId: args.importId };
      if (prior) await ctx.db.replace(prior._id, value);
      else await ctx.db.insert("aliases", value);
    }
    const prior = await ctx.db.query("library").withIndex("by_name", (q) => q.eq("name", "current")).unique();
    const meta = { name: "current", importId: args.importId, importedAt: Date.now(), claimCount: args.claims.length };
    if (prior) await ctx.db.replace(prior._id, meta);
    else await ctx.db.insert("library", meta);
    return { importId: args.importId, claims: args.claims.length, versions: args.versions.length };
  },
});

export const inspect = internalQuery({
  args: { claimId: v.string(), version: v.number(), recordHash: v.string() },
  returns: v.any(),
  handler: async (ctx, args) => {
    const claim = await ctx.db.query("claims").withIndex("by_claimId", (q) => q.eq("claimId", args.claimId)).unique();
    const meta = await ctx.db.query("library").withIndex("by_name", (q) => q.eq("name", "current")).unique();
    if (!claim || claim.importId !== meta?.importId) return { status: "not_in_library", answer: null };
    if (claim.state !== "approved" || claim.version !== args.version || claim.recordHash !== args.recordHash) {
      return { status: "withheld", answer: null, reason: "Current approval, version and hash must all match." };
    }
    const frozen = await ctx.db.query("recordVersions").withIndex("by_claimId_and_version", (q) =>
      q.eq("claimId", args.claimId).eq("version", args.version)).unique();
    if (!frozen || frozen.recordHash !== claim.recordHash) throw new Error("Missing frozen record");
    return { status: "record", evidence_package: claim.evidencePackage,
      frozen_record: JSON.parse(frozen.canonicalRecord), source_reviews: claim.sourceReviews,
      import_id: claim.importId, live_source_refresh: false };
  },
});

export const health = internalQuery({
  args: {}, returns: v.any(),
  handler: async (ctx) => {
    const meta = await ctx.db.query("library").withIndex("by_name", (q) => q.eq("name", "current")).unique();
    return { status: meta ? "ready" : "unseeded", claims: meta?.claimCount ?? 0,
      import_id: meta?.importId ?? null, implementation_review: "pending", version: "0.1.0" };
  },
});

import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export const publicationState = v.union(
  v.literal("approved"), v.literal("pending"), v.literal("reopened"),
  v.literal("retired"), v.literal("unselected"),
);
export const jobState = v.union(
  v.literal("not_started"), v.literal("in_progress"), v.literal("blocked"),
  v.literal("done"), v.literal("canceled"),
);

export default defineSchema({
  recordVersions: defineTable({
    claimId: v.string(), version: v.number(), recordHash: v.string(),
    canonicalRecord: v.string(),
  }).index("by_claimId_and_version", ["claimId", "version"]),
  claims: defineTable({
    claimId: v.string(), version: v.number(), recordHash: v.string(),
    state: publicationState, normalizedClaim: v.string(), searchText: v.string(), importId: v.string(),
    // The complete validated Python projection and source checks retain their
    // original schemas. The internal importer is the only writer.
    evidencePackage: v.any(), sourceReviews: v.any(),
  }).index("by_claimId", ["claimId"])
    .index("by_normalizedClaim", ["normalizedClaim"])
    .searchIndex("search_text", { searchField: "searchText", filterFields: ["state"] }),
  aliases: defineTable({
    normalizedText: v.string(), kind: v.union(v.literal("claim"), v.literal("clarify")),
    claimId: v.optional(v.string()), version: v.optional(v.number()),
    recordHash: v.optional(v.string()), clarification: v.optional(v.string()),
    importId: v.string(),
  }).index("by_normalizedText", ["normalizedText"]),
  library: defineTable({
    name: v.string(), importId: v.string(), importedAt: v.number(),
    claimCount: v.number(),
  }).index("by_name", ["name"]),
  jobs: defineTable({
    text: v.string(), normalizedText: v.string(), status: jobState,
    createdAt: v.number(), updatedAt: v.number(),
    tiloriPostId: v.optional(v.string()),
    worker: v.optional(v.string()), leaseUntil: v.optional(v.number()),
  }).index("by_normalizedText", ["normalizedText"])
    .index("by_status", ["status"])
    .index("by_status_and_leaseUntil", ["status", "leaseUntil"]),
  requestKeys: defineTable({
    key: v.string(), normalizedText: v.string(), jobId: v.id("jobs"),
  }).index("by_key", ["key"]),
});

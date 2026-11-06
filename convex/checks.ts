import { v } from "convex/values";
import { internalMutation, internalQuery } from "./_generated/server";
import { normalize } from "./contract";

export const check = internalMutation({
  args: { text: v.string(), publicReview: v.boolean(), requestKey: v.optional(v.string()) },
  returns: v.any(),
  handler: async (ctx, args) => {
    const key = normalize(args.text);
    if (!key || args.text.length > 4000) throw new Error("Invalid check text");
    const meta = await ctx.db.query("library").withIndex("by_name", (q) => q.eq("name", "current")).unique();
    if (!meta) return { status: "unavailable", answer: null, reason: "Library has not been imported." };
    const request = args.requestKey ? await ctx.db.query("requestKeys").withIndex("by_key", (q) =>
      q.eq("key", args.requestKey!)).unique() : null;
    if (request && request.normalizedText !== key) return { status: "conflict", answer: null };
    const base = { text: args.text, verdict: null, answer: null, import_id: meta.importId,
      live_source_refresh: false, implementation_review: "pending" };
    const alias = await ctx.db.query("aliases").withIndex("by_normalizedText", (q) => q.eq("normalizedText", key)).unique();
    const activeAlias = alias?.importId === meta.importId ? alias : null;
    if (activeAlias?.kind === "clarify") {
      return { ...base, status: "needs_clarification", reason: activeAlias.clarification };
    }
    let claim = activeAlias?.claimId ? await ctx.db.query("claims").withIndex("by_claimId", (q) =>
      q.eq("claimId", activeAlias.claimId!)).unique() : null;
    if (!activeAlias) {
      const matches = await ctx.db.query("claims").withIndex("by_normalizedClaim", (q) =>
        q.eq("normalizedClaim", key)).take(2);
      const active = matches.filter((item) => item.importId === meta.importId);
      if (active.length > 1) return { ...base, status: "needs_clarification", reason: "Several scoped records share this wording." };
      claim = active[0] ?? null;
    }
    if (claim && claim.importId === meta.importId) {
      if (claim.state !== "approved" || (activeAlias &&
          (activeAlias.version !== claim.version || activeAlias.recordHash !== claim.recordHash))) {
        return { ...base, status: "withheld", reason: "The exact mapped version is not currently approved." };
      }
      const kind = claim.evidencePackage.answer_kind;
      if (!["supported_assertion", "reviewed_abstention"].includes(kind)) {
        return { ...base, status: "withheld", reason: "Unsupported publication kind." };
      }
      return { ...base, status: kind === "reviewed_abstention" ? "abstain" : "answer",
        verdict: claim.evidencePackage.evidence_verdict, answer: claim.evidencePackage.answer,
        matching: activeAlias ? "reviewed_exact_alias" : "exact_record_claim",
        evidence_package: claim.evidencePackage,
        inspection: { claim_id: claim.claimId, version: claim.version, sha256: claim.recordHash } };
    }
    const hits = await ctx.db.query("claims").withSearchIndex("search_text", (q) =>
      q.search("searchText", args.text).eq("state", "approved")).take(8);
    const candidates = hits.filter((item) => item.importId === meta.importId).slice(0, 3).map((item) => ({
      claim_id: item.claimId, version: item.version, sha256: item.recordHash,
      claim: item.evidencePackage.claim_under_review, scope: item.evidencePackage.scope,
      scope_match_established: false,
    }));
    let job = null;
    if (args.publicReview) {
      let existing = await ctx.db.query("jobs").withIndex("by_normalizedText", (q) => q.eq("normalizedText", key)).unique();
      if (!existing) {
        const queued = await ctx.db.query("jobs").withIndex("by_status", (q) => q.eq("status", "not_started")).take(501);
        if (queued.length >= 500) return { ...base, status: "queue_full", candidates };
        const now = Date.now();
        const id = await ctx.db.insert("jobs", { text: args.text, normalizedText: key,
          status: "not_started", createdAt: now, updatedAt: now });
        existing = await ctx.db.get(id);
      }
      if (!existing) throw new Error("Research job missing");
      if (args.requestKey && !request) await ctx.db.insert("requestKeys", {
        key: args.requestKey, normalizedText: key, jobId: existing._id,
      });
      job = { id: existing._id, status: existing.status, tilori_post_id: existing.tiloriPostId ?? null };
    }
    return { ...base, status: "not_in_library", candidates, candidate_search: "full_text",
      reason: "No exact approved mapping. Candidates require scope and evidence review.", job };
  },
});

export const getJob = internalQuery({
  args: { id: v.string() }, returns: v.any(),
  handler: async (ctx, args) => {
    const id = ctx.db.normalizeId("jobs", args.id);
    const job = id ? await ctx.db.get(id) : null;
    if (!job) return null;
    return { id: job._id, text: job.text, status: job.status,
      created_at: job.createdAt, updated_at: job.updatedAt,
      tilori_post_id: job.tiloriPostId ?? null };
  },
});

export const listQueued = internalQuery({
  args: { now: v.number() }, returns: v.any(),
  handler: async (ctx, args) => {
    const queued = await ctx.db.query("jobs").withIndex("by_status", (q) => q.eq("status", "not_started")).take(10);
    const expired = await ctx.db.query("jobs").withIndex("by_status_and_leaseUntil", (q) =>
      q.eq("status", "in_progress").gt("leaseUntil", 0).lt("leaseUntil", args.now)).take(10);
    const jobs = [...queued, ...expired];
    return jobs.map((job) => ({ id: job._id, text: job.text, status: job.status,
      tilori_idempotency_key: `fact-ori-research-${job._id}` }));
  },
});

export const claimJob = internalMutation({
  args: { id: v.id("jobs"), worker: v.string() }, returns: v.any(),
  handler: async (ctx, args) => {
    const job = await ctx.db.get(args.id);
    const now = Date.now();
    if (!args.worker.trim() || args.worker.length > 120) throw new Error("Worker identifier required");
    if (!job || job.tiloriPostId || !["not_started", "in_progress"].includes(job.status) ||
        (job.leaseUntil && job.leaseUntil > now)) return null;
    await ctx.db.patch(job._id, { worker: args.worker, leaseUntil: now + 300000,
      status: "in_progress", updatedAt: now });
    return { id: job._id, text: job.text, tilori_idempotency_key: `fact-ori-research-${job._id}` };
  },
});

export const linkJob = internalMutation({
  args: { id: v.id("jobs"), worker: v.string(), postId: v.string() }, returns: v.null(),
  handler: async (ctx, args) => {
    const job = await ctx.db.get(args.id);
    if (!/^[a-f0-9-]{36}$/i.test(args.postId)) throw new Error("Tilori post ID required");
    if (job?.tiloriPostId === args.postId) return null;
    if (!job || job.worker !== args.worker || !job.leaseUntil || job.leaseUntil < Date.now() || job.tiloriPostId) {
      throw new Error("Active worker lease required");
    }
    await ctx.db.patch(job._id, { tiloriPostId: args.postId, leaseUntil: 0, updatedAt: Date.now() });
    return null;
  },
});

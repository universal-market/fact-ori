import { httpRouter } from "convex/server";
import { httpAction } from "./_generated/server";
import { internal } from "./_generated/api";
import { isDigest, normalize, validateText } from "./contract";
import { withImplementationProvenance } from "./provenance";

const http = httpRouter();
const headers = { "Content-Type": "application/json", "Cache-Control": "no-store",
  "Access-Control-Allow-Origin": "*" };
const json = (value: Record<string, unknown>, status = 200) =>
  new Response(JSON.stringify(withImplementationProvenance(value)), { status, headers });

http.route({ path: "/health", method: "GET", handler: httpAction(async (ctx) =>
  json(await ctx.runQuery(internal.library.health, {}))) });

http.route({ path: "/v1/check", method: "POST", handler: httpAction(async (ctx, request) => {
  let body;
  try {
    if (!request.headers.get("content-type")?.toLowerCase().includes("application/json")) {
      return json({ error: "Content-Type must be application/json" }, 415);
    }
    const raw = await request.text();
    if (raw.length > 12000) return json({ error: "Request too large" }, 413);
    body = JSON.parse(raw);
    if (!body || Array.isArray(body) || typeof body !== "object" ||
        Object.keys(body).some((key) => !["text", "public_review"].includes(key))) {
      return json({ error: "Expected text and optional public_review" }, 400);
    }
    validateText(body.text);
    if (!normalize(body.text) || (body.public_review !== undefined && typeof body.public_review !== "boolean")) {
      return json({ error: "Invalid text or public_review" }, 400);
    }
  } catch {
    return json({ error: "Expected JSON with text containing 1–4000 characters" }, 400);
  }
  const requestKey = request.headers.get("idempotency-key") ?? undefined;
  if (requestKey !== undefined && (!requestKey.trim() || requestKey.length > 128)) {
    return json({ error: "Idempotency-Key must contain 1–128 characters" }, 400);
  }
  if (process.env.FACT_ORI_PUBLIC_READ_ONLY === "true" && body.public_review === true) {
    return json({ error: "Public research intake is disabled on this deployment." }, 403);
  }
  try {
    const result = await ctx.runMutation(internal.checks.check, {
      text: body.text, publicReview: body.public_review ?? false, ...(requestKey ? { requestKey } : {}),
    });
    const status = result.status === "conflict" ? 409 :
      ["queue_full", "unavailable"].includes(result.status) ? 503 :
        ("job" in result && result.job) ? 202 : 200;
    return json(result, status);
  } catch {
    return json({ error: "Library check unavailable" }, 503);
  }
}) });

http.route({ pathPrefix: "/v1/records/", method: "GET", handler: httpAction(async (ctx, request) => {
  const url = new URL(request.url);
  const claimId = url.pathname.slice("/v1/records/".length);
  const version = Number(url.searchParams.get("version"));
  const recordHash = url.searchParams.get("sha256") ?? "";
  if (!/^C[0-9]+[a-z]?$/.test(claimId) || !Number.isSafeInteger(version) || version < 1 || !isDigest(recordHash)) {
    return json({ error: "Supply claim ID, positive version and sha256" }, 400);
  }
  try {
    const result = await ctx.runQuery(internal.library.inspect, { claimId, version, recordHash });
    return json(result, result.status === "not_in_library" ? 404 : result.status === "withheld" ? 409 : 200);
  } catch { return json({ error: "Record inspection unavailable" }, 503); }
}) });

http.route({ pathPrefix: "/v1/jobs/", method: "GET", handler: httpAction(async (ctx, request) => {
  const id = new URL(request.url).pathname.slice("/v1/jobs/".length);
  const job = await ctx.runQuery(internal.checks.getJob, { id });
  return job ? json(job) : json({ error: "Job not found" }, 404);
}) });

http.route({ pathPrefix: "/v1/", method: "OPTIONS", handler: httpAction(async () =>
  new Response(null, { status: 204, headers: { ...headers,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Idempotency-Key" } })) });

export default http;

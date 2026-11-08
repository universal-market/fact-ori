import { ConvexHttpClient } from "convex/browser";
import { makeFunctionReference } from "convex/server";
const queries = new Set([
  "checks:listQueued",
  "checks:listForReconciliation",
  "checks:getJob",
  "library:health",
]);
const mutations = new Set([
  "checks:claimJob",
  "checks:linkJob",
  "checks:reconcileJob",
]);
const [name, raw] = process.argv.slice(2);
if (!queries.has(name) && !mutations.has(name))
  throw new Error("Unsupported Fact-ori operator function");
if (!raw || raw.length > 16000)
  throw new Error("Operator JSON arguments required");
const args = JSON.parse(raw);
const client = new ConvexHttpClient(process.env.CONVEX_SELF_HOSTED_URL);
client.setAdminAuth(process.env.CONVEX_SELF_HOSTED_ADMIN_KEY);
const result = await client[queries.has(name) ? "query" : "mutation"](
  makeFunctionReference(name),
  args,
);
console.log(JSON.stringify(result));

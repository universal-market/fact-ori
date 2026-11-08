#!/bin/sh
# Key arrives on stdin from this instance, never argv, logs, image or host env.
set -eu
IFS= read -r CONVEX_SELF_HOSTED_ADMIN_KEY
export CONVEX_SELF_HOSTED_ADMIN_KEY
export HOME=/tmp/factori-deploy
export CONVEX_SELF_HOSTED_URL=http://backend:3210
export CONVEX_DISABLE_TELEMETRY=1
mkdir -p "$HOME"
# Set BEFORE pushing public routes; no inherited CLI login or default target.
./node_modules/.bin/convex env set FACT_ORI_PUBLIC_READ_ONLY true
./node_modules/.bin/convex dev --once --typecheck disable
node --input-type=module -e '
import { readFileSync } from "node:fs";
import { ConvexHttpClient } from "convex/browser";
import { makeFunctionReference } from "convex/server";
const seed = JSON.parse(readFileSync("seed.json", "utf8"));
const client = new ConvexHttpClient(process.env.CONVEX_SELF_HOSTED_URL);
client.setAdminAuth(process.env.CONVEX_SELF_HOSTED_ADMIN_KEY);
const result = await client.mutation(makeFunctionReference("library:importSnapshot"), seed);
console.log(JSON.stringify(result));
'

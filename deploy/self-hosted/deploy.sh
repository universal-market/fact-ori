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
import { spawnSync } from "node:child_process";
const seed = JSON.parse(readFileSync("seed.json", "utf8"));
const child = spawnSync("./node_modules/.bin/convex", ["run", "library:importSnapshot", JSON.stringify(seed)], {stdio:"inherit"});
process.exit(child.status ?? 1);
'

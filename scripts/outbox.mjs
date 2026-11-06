import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const result = spawnSync("npx", ["convex", "run", "checks:listQueued", JSON.stringify({ now: Date.now() })], {
  cwd: fileURLToPath(new URL("../", import.meta.url)), stdio: "inherit",
});
process.exit(result.status ?? 1);

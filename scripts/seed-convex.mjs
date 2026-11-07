import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { python } from "./python.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const exported = spawnSync(python(), ["-B", "scripts/export_api_seed.py"], {
  cwd: root, encoding: "utf8", maxBuffer: 8 * 1024 * 1024,
});
if (exported.status !== 0) {
  process.stderr.write(exported.stderr);
  process.exit(exported.status ?? 1);
}
const snapshot = JSON.parse(exported.stdout);
const imported = spawnSync("npx", ["convex", "run", "library:importSnapshot", JSON.stringify(snapshot)], {
  cwd: root, stdio: "inherit",
});
process.exit(imported.status ?? 1);

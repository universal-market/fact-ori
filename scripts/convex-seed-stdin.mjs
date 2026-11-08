// Keep the exported public library off the OS argument vector. The installed
// Convex CLI still owns normal deployment selection/authentication internally.
import { readFileSync } from "node:fs";
const raw = readFileSync(0, "utf8");
JSON.parse(raw);
process.argv = [
  process.execPath,
  "convex",
  "run",
  "library:importSnapshot",
  raw,
];
await import("../node_modules/convex/dist/cli.bundle.cjs");

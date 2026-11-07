// Resolve a Python 3 interpreter portably. Some systems (Debian/Ubuntu,
// macOS since 12.3) ship `python3` but no `python`; others only `python`.
// Order: $PYTHON if set, then `python3`, then `python`.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export function python() {
  const candidates = process.env.PYTHON ? [process.env.PYTHON] : ["python3", "python"];
  for (const cmd of candidates) {
    const probe = spawnSync(cmd, ["-c", "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)"]);
    if (probe.status === 0) return cmd;
  }
  throw new Error(`No Python 3 interpreter found (tried: ${candidates.join(", ")}). Set PYTHON to override.`);
}

// CLI: `node scripts/python.mjs <args...>` runs the resolved interpreter.
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const run = spawnSync(python(), process.argv.slice(2), { stdio: "inherit" });
  process.exit(run.status ?? 1);
}

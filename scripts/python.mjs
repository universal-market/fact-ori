// Resolve a Python interpreter portably. Some systems (Debian/Ubuntu, macOS
// since 12.3) ship `python3` but no `python`; others only `python`.
//
// If PYTHON is set, it must name one executable (a path or a name on PATH, not
// a shell command with flags) running Python >= 3.10, or resolution fails: an
// explicit override is never silently replaced. Otherwise `python3`, then
// `python`, is the first one that runs Python >= 3.10. Interpreters are spawned
// with an argv array, never through a shell.
import { spawnSync } from "node:child_process";
import { constants } from "node:os";
import { fileURLToPath } from "node:url";

export const MIN_VERSION = [3, 10];
const PROBE = "import sys; print('%d.%d' % sys.version_info[:2])";

function probe(cmd, env) {
  const run = spawnSync(cmd, ["-c", PROBE], { env, encoding: "utf8" });
  if (run.error || run.status !== 0) return { ok: false, why: run.error ? run.error.code ?? run.error.message : `exit ${run.status}` };
  const m = /^(\d+)\.(\d+)\s*$/.exec(run.stdout);
  if (!m) return { ok: false, why: `unrecognised version output ${JSON.stringify(run.stdout.trim())}` };
  const [major, minor] = [Number(m[1]), Number(m[2])];
  const ok = major > MIN_VERSION[0] || (major === MIN_VERSION[0] && minor >= MIN_VERSION[1]);
  return { ok, why: ok ? "" : `Python ${major}.${minor} is older than ${MIN_VERSION.join(".")}` };
}

export function python(env = process.env) {
  const want = MIN_VERSION.join(".");
  if (env.PYTHON !== undefined && env.PYTHON !== "") {
    const r = probe(env.PYTHON, env);
    if (r.ok) return env.PYTHON;
    throw new Error(`PYTHON=${JSON.stringify(env.PYTHON)} is not a usable Python >= ${want} (${r.why}). PYTHON must name one executable, not a command with flags.`);
  }
  const tried = [];
  for (const cmd of ["python3", "python"]) {
    const r = probe(cmd, env);
    if (r.ok) return cmd;
    tried.push(`${cmd}: ${r.why}`);
  }
  throw new Error(`No Python >= ${want} found (${tried.join("; ")}). Install one or set PYTHON to its path.`);
}

// CLI: `node scripts/python.mjs <args...>` runs the resolved interpreter and
// exits with its status (128 + signal number if it was killed by a signal).
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  let cmd;
  try {
    cmd = python();
  } catch (e) {
    console.error(e.message);
    process.exit(127);
  }
  const run = spawnSync(cmd, process.argv.slice(2), { stdio: "inherit" });
  if (run.error) {
    console.error(run.error.message);
    process.exit(127);
  }
  process.exit(run.status ?? 128 + (constants.signals[run.signal] ?? 0));
}

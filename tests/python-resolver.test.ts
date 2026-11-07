// @vitest-environment node
import { afterAll, describe, expect, test } from "vitest";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { python } from "../scripts/python.mjs";

const cli = fileURLToPath(new URL("../scripts/python.mjs", import.meta.url));
const realPython = spawnSync("sh", ["-c", "command -v python3 || command -v python"], { encoding: "utf8" }).stdout.trim();
const root = mkdtempSync(join(tmpdir(), "fact-ori-python-"));
afterAll(() => rmSync(root, { recursive: true, force: true }));

let n = 0;
// A directory to use as the whole PATH, holding the given interpreters.
function binDir(entries: Record<string, "real" | "old">, name = `bin${n++}`) {
  const dir = join(root, name);
  mkdirSync(dir, { recursive: true });
  for (const [file, kind] of Object.entries(entries)) {
    const path = join(dir, file);
    if (kind === "real") symlinkSync(realPython, path);
    else {
      writeFileSync(path, "#!/bin/sh\necho 3.8\n");
      chmodSync(path, 0o755);
    }
  }
  return dir;
}
const env = (dir: string, extra: Record<string, string> = {}) => ({ PATH: dir, ...extra });

describe.skipIf(!realPython)("Python interpreter resolution", () => {
  test("python3-only PATH resolves python3", () => {
    expect(python(env(binDir({ python3: "real" })))).toBe("python3");
  });
  test("python-only PATH falls back to python", () => {
    expect(python(env(binDir({ python: "real" })))).toBe("python");
  });
  test("a too-old python3 is skipped in favour of python", () => {
    expect(python(env(binDir({ python3: "old", python: "real" })))).toBe("python");
  });
  test("a valid explicit PYTHON path, including spaces, is used", () => {
    const dir = binDir({ "my python": "real" }, "dir with spaces");
    const explicit = join(dir, "my python");
    expect(python(env(binDir({}), { PYTHON: explicit }))).toBe(explicit);
  });
  test("an invalid explicit PYTHON is an error, not a fallback", () => {
    const path = binDir({ python3: "real" });
    expect(() => python(env(path, { PYTHON: join(root, "missing") }))).toThrow(/PYTHON=.*not a usable/);
    expect(() => python(env(path, { PYTHON: "python3 -B" }))).toThrow(/not a command with flags/);
  });
  test("a too-old explicit PYTHON is an error", () => {
    const old = join(binDir({ py: "old" }), "py");
    expect(() => python(env(binDir({ python3: "real" }), { PYTHON: old }))).toThrow(/3\.8 is older than 3\.10/);
  });
  test("neither interpreter is an error", () => {
    expect(() => python(env(binDir({})))).toThrow(/No Python >= 3\.10 found/);
  });
  test("CLI propagates the interpreter's nonzero exit status", () => {
    const run = spawnSync(process.execPath, [cli, "-c", "import sys; sys.exit(7)"], { env: env(binDir({ python3: "real" })) });
    expect(run.status).toBe(7);
  });
  test("CLI exits 127 when no interpreter is found", () => {
    const run = spawnSync(process.execPath, [cli, "-c", "pass"], { env: env(binDir({})), encoding: "utf8" });
    expect(run.status).toBe(127);
    expect(run.stderr).toMatch(/No Python >= 3\.10 found/);
  });
});

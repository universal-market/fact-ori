import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  mkdtempSync,
  mkdirSync,
  copyFileSync,
  writeFileSync,
  rmSync,
} from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
test("large library reaches the CLI unchanged without OS argument limits or credentials", () => {
  const dir = mkdtempSync(join(tmpdir(), "factori-seed-"));
  try {
    mkdirSync(join(dir, "scripts"));
    mkdirSync(join(dir, "node_modules/convex/dist"), { recursive: true });
    copyFileSync(
      new URL("./convex-seed-stdin.mjs", import.meta.url),
      join(dir, "scripts/convex-seed-stdin.mjs"),
    );
    writeFileSync(
      join(dir, "node_modules/convex/dist/cli.bundle.cjs"),
      `const{createHash}=require('node:crypto');console.log(JSON.stringify({command:process.argv[2],name:process.argv[3],sha256:createHash('sha256').update(process.argv[4]).digest('hex')}));`,
    );
    const raw = JSON.stringify({ public_fixture: "x".repeat(1024 * 1024) });
    const run = spawnSync(
      process.execPath,
      [join(dir, "scripts/convex-seed-stdin.mjs")],
      { input: raw, encoding: "utf8" },
    );
    assert.equal(run.status, 0, run.stderr);
    assert.deepEqual(JSON.parse(run.stdout), {
      command: "run",
      name: "library:importSnapshot",
      sha256: createHash("sha256").update(raw).digest("hex"),
    });
    const invalid = spawnSync(
      process.execPath,
      [join(dir, "scripts/convex-seed-stdin.mjs")],
      { input: "not-json", encoding: "utf8" },
    );
    assert.notEqual(invalid.status, 0);
    assert.equal(invalid.stdout, "");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

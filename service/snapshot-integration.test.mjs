import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync, writeFileSync, mkdtempSync, rmSync, existsSync, copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { FactEngine, engineFingerprint, digest } from "./engine.mjs";
const library = JSON.parse(readFileSync(new URL("../public/library.json", import.meta.url)));
const offline = JSON.parse(readFileSync(new URL("../scripts/fixtures/c007a-v3/pending-consumer-results-v1.json", import.meta.url)));
const invalid = { code: "INVALID_PUBLIC_SNAPSHOT" };
function fixture() {
  const db = new DatabaseSync(":memory:");
  let embeddings = 0;
  const engine = new FactEngine({ snapshot: structuredClone(library), db,
    model: { embeddingModel: "stub", embed: async (texts) => {
      embeddings += texts.length; return texts.map(() => [1, 1]);
    } }, backend: "http://unused.invalid" });
  return { engine, db, embeddings: () => embeddings };
}

test("unsupported constructor snapshots reject before any DB or model work", () => {
  for (const snapshot of [offline.seed, offline.export, { ...library, schema_version: 2 }]) {
    let calls = 0;
    assert.throws(() => new FactEngine({ snapshot,
      db: { exec: () => calls++ }, model: { embed: () => calls++ } }), invalid);
    assert.equal(calls, 0);
  }
});
test("initialization validates whole snapshot before first vector; rejected reinit clears candidates", async () => {
  const f = fixture();
  try {
    f.engine.snapshot.records.at(-1).evidence_package.state = "pending";
    await assert.rejects(f.engine.initialize(), invalid);
    assert.equal(f.embeddings(), 0);
    assert.equal(f.db.prepare("SELECT count(*) AS n FROM vectors").get().n, 0);
    f.engine.snapshot = structuredClone(library);
    await f.engine.initialize();
    assert.equal(f.engine.records.length, 8);
    const count = f.embeddings();
    f.engine.snapshot = offline.export;
    await assert.rejects(f.engine.initialize(), invalid);
    assert.deepEqual(f.engine.records, []);
    assert.equal(f.embeddings(), count);
    assert.equal(f.db.prepare("SELECT count(*) AS n FROM vectors").get().n, 8);
  } finally { f.db.close(); }
});
test("valid eight-record initialization and warm reinit preserve cache; empty index is valid", async () => {
  const f = fixture();
  try {
    await f.engine.initialize();
    assert.equal(f.embeddings(), 8);
    await f.engine.initialize();
    assert.equal(f.embeddings(), 8);
    assert.deepEqual(f.engine.records.map((r) => r.claim_id), library.records.map((r) => r.claim_id));
    f.engine.snapshot = { ...library, records: [], exact_mappings: [] };
    await f.engine.initialize();
    assert.deepEqual(f.engine.records, []);
    assert.equal(f.embeddings(), 8);
  } finally { f.db.close(); }
});
test("invalid server startup/restart leaves state untouched, never listens and hides parser excerpts", () => {
  const dir = mkdtempSync(join(tmpdir(), "factori-snapshot-startup-"));
  try {
    const state = join(dir, "state.sqlite"), path = join(dir, "snapshot.json");
    const run = () => spawnSync(process.execPath, ["service/server.mjs"], {
      env: { PATH: process.env.PATH, STATE_PATH: state, LIBRARY_PATH: path,
        PORT: "0", MODEL_ORIGIN: "http://127.0.0.1:1", EVIDENCE_ORIGIN: "http://127.0.0.1:1" },
      encoding: "utf8", timeout: 5000,
    });
    for (const value of [JSON.stringify(offline.seed), JSON.stringify(offline.export), '{"private-marker-untrusted":']) {
      writeFileSync(path, value);
      const child = run();
      assert.ifError(child.error);
      assert.notEqual(child.status, 0);
      assert.match(child.stderr, /INVALID_PUBLIC_SNAPSHOT/);
      assert(!child.stderr.includes("private-marker-untrusted"));
      assert(!child.stdout.includes("listening"));
      assert.equal(existsSync(state), false);
    }
    const db = new DatabaseSync(state);
    db.exec("CREATE TABLE requests(id TEXT PRIMARY KEY,state TEXT,result TEXT); INSERT INTO requests VALUES('old','processing','old-result')");
    db.close();
    writeFileSync(path, JSON.stringify(offline.export));
    for (let i = 0; i < 2; i++) {
      const child = run(); assert.ifError(child.error); assert.notEqual(child.status, 0);
      const check = new DatabaseSync(state);
      assert.deepEqual(check.prepare("PRAGMA table_info(requests)").all().map((r) => r.name), ["id", "state", "result"]);
      assert.equal(check.prepare("SELECT result FROM requests").get().result, "old-result");
      assert.equal(check.prepare("SELECT state FROM requests").get().state, "processing");
      assert.equal(check.prepare("SELECT count(*) AS n FROM sqlite_master WHERE name='vectors'").get().n, 0);
      check.close();
    }
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
test("engine fingerprint binds guard bytes as well as engine/server/model files", () => {
  const names = ["engine.mjs", "server.mjs", "models.json", "snapshot-boundary.mjs"];
  assert.equal(engineFingerprint(), digest(names.map((name) => readFileSync(new URL(name, import.meta.url), "utf8")).join("\n")));
  const dir = mkdtempSync(join(tmpdir(), "factori-guard-fingerprint-"));
  try {
    for (const name of names) copyFileSync(new URL(name, import.meta.url), join(dir, name));
    const run = () => {
      const x = spawnSync(process.execPath, ["--input-type=module", "-e",
        `import {engineFingerprint} from ${JSON.stringify("file://" + resolve(dir, "engine.mjs"))}; console.log(engineFingerprint());`],
      { encoding: "utf8", timeout: 5000 });
      assert.ifError(x.error); assert.equal(x.status, 0); return x.stdout.trim();
    };
    assert.equal(run(), engineFingerprint());
    writeFileSync(join(dir, "snapshot-boundary.mjs"), readFileSync(join(dir, "snapshot-boundary.mjs"), "utf8") + "\n// fingerprint mutation\n");
    assert.notEqual(run(), engineFingerprint());
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

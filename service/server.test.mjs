import test from "node:test";
import { DatabaseSync } from "node:sqlite";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
const pins = JSON.parse(
  readFileSync(new URL("./models.json", import.meta.url)),
);
const snapshot = JSON.parse(
  readFileSync(new URL("../public/library.json", import.meta.url)),
);
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
test("durable HTTP analysis: consent, idempotency, restart, status and revision invalidation", async () => {
  const directory = mkdtempSync(join(tmpdir(), "factori-http-"));
  let child;
  let delay = 0;
  let submissions = 0;
  let importId = snapshot.library_import_id;
  const upstream = createServer(async (req, res) => {
    let input = "";
    for await (const chunk of req) input += chunk;
    const body = input ? JSON.parse(input) : {};
    let result;
    if (req.url === "/api/tags")
      result = {
        models: Object.entries(pins).map(([name, digest]) => ({
          name,
          digest,
        })),
      };
    else if (req.url === "/api/embed")
      result = { embeddings: body.input.map(() => Array(768).fill(1)) };
    else if (req.url === "/api/chat") {
      await pause(delay);
      result = {
        message: {
          content: JSON.stringify(
            body.format.properties.claims
              ? {
                  claims: [
                    {
                      source_quote: JSON.parse(body.messages[1].content).text,
                      claim: JSON.parse(body.messages[1].content).text,
                    },
                  ],
                }
              : body.format.properties.coverage
                ? { coverage: "atomic_text_preserved", reason: "Covered" }
                : {
                    relationship: "different_subject_or_predicate",
                    reason: "Uncovered predicate",
                    scope_difference: "",
                  },
          ),
        },
      };
    } else if (req.url === "/health")
      result = {
        status: "ready",
        import_id: importId,
        public_intake: "enabled",
      };
    else if (req.url === "/v1/check") {
      if (body.public_review) submissions++;
      result = {
        status: "not_in_library",
        ...(body.public_review
          ? { job: { id: "test-research-job", status: "not_started" } }
          : {}),
      };
    } else {
      res.statusCode = 404;
      result = {};
    }
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify(result));
  });
  await new Promise((r) => upstream.listen(0, "127.0.0.1", r));
  const upstreamOrigin = `http://127.0.0.1:${upstream.address().port}`;
  const portServer = createServer();
  await new Promise((r) => portServer.listen(0, "127.0.0.1", r));
  const port = portServer.address().port;
  await new Promise((r) => portServer.close(r));
  const origin = `http://127.0.0.1:${port}`;
  async function start() {
    child = spawn(process.execPath, ["service/server.mjs"], {
      env: {
        PATH: process.env.PATH,
        PORT: String(port),
        STATE_PATH: join(directory, "state.sqlite"),
        MODEL_ORIGIN: upstreamOrigin,
        EVIDENCE_ORIGIN: upstreamOrigin,
        LIBRARY_PATH: resolve("public/library.json"),
        OPENAPI_PATH: resolve("public/openapi.json"),
      },
      stdio: "ignore",
    });
    for (let n = 0; n < 100; n++) {
      try {
        if ((await fetch(origin + "/health")).ok) return;
      } catch {}
      await pause(30);
    }
    throw Error("Service not ready");
  }
  async function stop() {
    if (child && child.exitCode === null) {
      const exited = new Promise((r) => child.once("exit", r));
      child.kill("SIGTERM");
      await exited;
    }
  }
  async function post(input, key) {
    return fetch(origin + "/v1/check", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(key ? { "Idempotency-Key": key } : {}),
      },
      body: JSON.stringify(input),
    });
  }
  async function complete(path) {
    for (let n = 0; n < 100; n++) {
      const r = await fetch(origin + path);
      const b = await r.json();
      if (b.status === "complete") return b;
      assert.notEqual(b.status, "failed");
      await pause(30);
    }
    throw Error("No completion");
  }
  try {
    await start();
    const spec = await (await fetch(origin + "/openapi.json")).json();
    assert.equal(spec.openapi, "3.1.0");
    assert.ok(spec.paths["/v1/check"].post.requestBody);
    assert.equal((await post({ text: "x", unexpected: true })).status, 400);
    delay = 200;
    const input = { text: "Do unicorns live on Mars?", async: true };
    const initial = await post(input, "stable");
    assert.equal(initial.status, 202);
    const queued = await initial.json();
    assert.equal(
      (await post({ ...input, text: "Different text" }, "stable")).status,
      409,
    );
    const replay = await (await post(input, "stable")).json();
    assert.equal(replay.id, queued.id);
    await stop();
    delay = 0;
    await start();
    const done = await complete(queued.poll_url);
    assert.equal(done.result.status, "not_in_library");
    assert.equal(submissions, 0);
    const research = await (
      await post({ ...input, public_review: true }, "research")
    ).json();
    const researched = await complete(research.poll_url);
    assert.equal(researched.result.job.id, "test-research-job");
    assert.equal(submissions, 1);
    importId = "new-library";
    assert.equal((await fetch(origin + queued.poll_url)).status, 409);
    assert.equal((await post(input, "stable")).status, 409);
    const stateDb = new DatabaseSync(join(directory, "state.sqlite"));
    for (const state of ["processing", "failed"]) {
      stateDb.prepare("UPDATE requests SET state=?,result=? WHERE id=?").run(
        state,
        JSON.stringify({
          import_id: snapshot.library_import_id,
          results: [{ status: "answer", answer: "stale answer" }],
        }),
        queued.id,
      );
      const stale = await fetch(origin + queued.poll_url);
      assert.equal(stale.status, 409);
      assert.equal((await stale.json()).results, undefined);
      assert.equal((await post(input, "stable")).status, 409);
    }
    importId = snapshot.library_import_id;
    stateDb
      .prepare(
        "UPDATE requests SET engine_revision='previous-engine' WHERE id=?",
      )
      .run(queued.id);
    assert.equal((await fetch(origin + queued.poll_url)).status, 409);
    assert.equal((await post(input, "stable")).status, 409);
    stateDb.close();
  } finally {
    await stop();
    await new Promise((r) => upstream.close(r));
    rmSync(directory, { recursive: true, force: true });
  }
});

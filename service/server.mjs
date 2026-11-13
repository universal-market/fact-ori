import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { randomUUID } from "node:crypto";
import {
  FactEngine,
  ModelClient,
  digest,
  engineFingerprint,
} from "./engine.mjs";

// Reject unsupported input before opening/migrating state, listening or model I/O.
import { assertPublicSnapshot } from "./snapshot-boundary.mjs";
const snapshot = (() => {
  let value;
  try {
    value = JSON.parse(readFileSync(
      process.env.LIBRARY_PATH ?? new URL("./library.json", import.meta.url), "utf8",
    ));
  } catch {
    // Do not include file contents, parser excerpts or paths in the diagnostic.
    const error = new Error("Cannot load public evidence snapshot");
    error.code = "INVALID_PUBLIC_SNAPSHOT";
    throw error;
  }
  assertPublicSnapshot(value);
  return value;
})();

const db = new DatabaseSync(process.env.STATE_PATH ?? "/state/semantic.sqlite");
db.exec(`PRAGMA journal_mode=WAL;
 CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, request_key TEXT UNIQUE, fingerprint TEXT NOT NULL,
 input TEXT NOT NULL, state TEXT NOT NULL, result TEXT, created INTEGER NOT NULL, updated INTEGER NOT NULL);
`);
const model = new ModelClient(
  process.env.MODEL_ORIGIN ?? "http://inference:11434",
  process.env.CHAT_MODEL ?? "qwen2.5:14b-instruct",
  process.env.EMBEDDING_MODEL ?? "nomic-embed-text:v1.5",
);
const backend = process.env.EVIDENCE_ORIGIN ?? "http://backend:3211";
const modelPins = JSON.parse(
  readFileSync(new URL("./models.json", import.meta.url)),
);
const engineRevision = engineFingerprint();
if (
  !db
    .prepare("PRAGMA table_info(requests)")
    .all()
    .some((column) => column.name === "engine_revision")
)
  db.exec("ALTER TABLE requests ADD COLUMN engine_revision TEXT");
// Recompute interrupted work with this engine; never mix partial judgments from revisions.
db.prepare(
  "UPDATE requests SET state='queued',result=NULL,engine_revision=? WHERE state IN ('queued','processing')",
).run(engineRevision);
const engine = new FactEngine({ snapshot, model, db, backend });
let ready = false,
  working = false;
const cors = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Cache-Control": "no-store",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Idempotency-Key",
};
function send(res, status, body) {
  res.writeHead(status, cors);
  res.end(body === null ? "" : JSON.stringify(body));
}
function progress(row) {
  const result = row.result ? JSON.parse(row.result) : null;
  return {
    status:
      row.state === "completed"
        ? "complete"
        : row.state === "failed"
          ? "failed"
          : "processing",
    id: row.id,
    engine_revision: row.engine_revision,
    poll_url: `/v1/checks/${row.id}`,
    created_at: row.created,
    updated_at: row.updated,
    ...(row.state === "completed"
      ? { result }
      : { results: result?.results ?? [] }),
    ...(row.state === "failed"
      ? {
          error:
            result?.error ??
            "Analysis failed. Retry later or inspect service readiness.",
        }
      : {}),
  };
}
async function pump() {
  if (working || !ready) return;
  working = true;
  try {
    let row;
    while (
      (row = db
        .prepare(
          "SELECT * FROM requests WHERE state='queued' ORDER BY created LIMIT 1",
        )
        .get())
    ) {
      db.prepare(
        "UPDATE requests SET state='processing',updated=? WHERE id=?",
      ).run(Date.now(), row.id);
      try {
        const result = await engine.run(
          JSON.parse(row.input),
          (results, import_id) => {
            db.prepare("UPDATE requests SET result=?,updated=? WHERE id=?").run(
              JSON.stringify({
                results,
                import_id,
                engine_revision: engineRevision,
              }),
              Date.now(),
              row.id,
            );
          },
        );
        result.engine_revision = engineRevision;
        db.prepare(
          "UPDATE requests SET state='completed',result=?,updated=? WHERE id=?",
        ).run(JSON.stringify(result), Date.now(), row.id);
      } catch (error) {
        console.error(
          JSON.stringify({
            event: "analysis_failed",
            id: row.id,
            error: error.message,
          }),
        );
        const partial = db
          .prepare("SELECT result FROM requests WHERE id=?")
          .get(row.id);
        const results = partial.result
          ? JSON.parse(partial.result).results
          : [];
        db.prepare(
          "UPDATE requests SET state='failed',result=?,updated=? WHERE id=?",
        ).run(
          JSON.stringify({
            results,
            import_id: partial.result
              ? JSON.parse(partial.result).import_id
              : snapshot.library_import_id,
            error: error.message,
          }),
          Date.now(),
          row.id,
        );
      }
    }
  } finally {
    working = false;
  }
}
const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://semantic");
    db.prepare(
      "DELETE FROM requests WHERE state IN ('completed','failed') AND created<?",
    ).run(Date.now() - 86400000);
    if (req.method === "OPTIONS") {
      send(res, 204, null);
      return;
    }
    if (req.method === "GET" && url.pathname === "/openapi.json") {
      send(
        res,
        200,
        JSON.parse(
          readFileSync(
            process.env.OPENAPI_PATH ??
              new URL("./openapi.json", import.meta.url),
          ),
        ),
      );
      return;
    }
    if (req.method === "GET" && url.pathname === "/health") {
      const health = await engine.backendJson("/health");
      const current = ready && health.import_id === snapshot.library_import_id;
      send(res, current ? 200 : 503, {
        ...health,
        status: current && health.status === "ready" ? "ready" : "initializing",
        engine_revision: engineRevision,
        model_configuration: {
          chat_model: model.chatModel,
          chat_revision: model.chatRevision ?? null,
          embedding_model: model.embeddingModel,
          embedding_revision: model.embeddingRevision ?? null,
        },
        semantic_search: ready,
        claim_decomposition: ready,
        chat_model: model.chatModel,
        embedding_model: model.embeddingModel,
        analysis_queue: db
          .prepare(
            "SELECT count(*) AS n FROM requests WHERE state IN ('queued','processing')",
          )
          .get().n,
      });
      return;
    }
    if (
      req.method === "GET" &&
      /^\/v1\/checks\/[a-f0-9-]{36}$/.test(url.pathname)
    ) {
      const row = db
        .prepare("SELECT * FROM requests WHERE id=?")
        .get(url.pathname.split("/").at(-1));
      if (row && row.engine_revision !== engineRevision) {
        send(res, 409, {
          id: row.id,
          status: "stale",
          reason:
            "Analysis engine changed. Submit a new analysis with a new request key.",
        });
        return;
      }
      if (row?.result) {
        const health = await engine.backendJson("/health");
        if (JSON.parse(row.result).import_id !== health.import_id) {
          send(res, 409, {
            id: row.id,
            status: "stale",
            reason: "Library changed. Submit a new analysis.",
          });
          return;
        }
      }
      send(
        res,
        row ? 200 : 404,
        row ? progress(row) : { error: "Analysis not found" },
      );
      return;
    }
    if (req.method !== "POST" || url.pathname !== "/v1/check") {
      send(res, 404, { error: "Not found" });
      return;
    }
    if (!ready) {
      send(res, 503, { error: "Semantic models are initializing" });
      return;
    }
    if (
      !req.headers["content-type"]?.toLowerCase().includes("application/json")
    ) {
      send(res, 415, { error: "Content-Type must be application/json" });
      return;
    }
    const chunks = [];
    let bytes = 0;
    for await (const chunk of req) {
      chunks.push(chunk);
      bytes += chunk.length;
      if (bytes > 16000) {
        send(res, 413, { error: "Request too large" });
        return;
      }
    }
    let input;
    try {
      input = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    } catch {
      send(res, 400, { error: "Invalid JSON" });
      return;
    }
    if (
      !input ||
      Array.isArray(input) ||
      Object.keys(input).some(
        (k) => !["text", "public_review", "async"].includes(k),
      ) ||
      typeof input.text !== "string" ||
      !input.text.trim() ||
      input.text.length > 4000 ||
      (input.public_review !== undefined &&
        typeof input.public_review !== "boolean") ||
      (input.async !== undefined && typeof input.async !== "boolean")
    ) {
      send(res, 400, {
        error:
          "Expected text (1–4000 characters), optional public_review and async booleans",
      });
      return;
    }
    const key = req.headers["idempotency-key"];
    if (
      key !== undefined &&
      (typeof key !== "string" || !key.trim() || key.length > 128)
    ) {
      send(res, 400, { error: "Invalid Idempotency-Key" });
      return;
    }
    const exact = await engine.backendJson("/v1/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: input.text, public_review: false }),
    });
    if (
      ["answer", "abstain", "needs_clarification", "withheld"].includes(
        exact.status,
      )
    ) {
      send(res, 200, {
        ...exact,
        engine_revision: engineRevision,
        results: [
          {
            claim: input.text,
            source_quote: input.text,
            start: 0,
            end: input.text.length,
            ...exact,
          },
        ],
      });
      return;
    }
    const fingerprint = digest(
      JSON.stringify({
        text: input.text,
        public_review: input.public_review ?? false,
      }),
    );
    let row = key
      ? db.prepare("SELECT * FROM requests WHERE request_key=?").get(key)
      : null;
    if (row && row.fingerprint !== fingerprint) {
      send(res, 409, {
        error: "Idempotency-Key already used for a different request",
      });
      return;
    }
    if (row && row.engine_revision !== engineRevision) {
      send(res, 409, {
        id: row.id,
        status: "stale",
        reason:
          "Analysis engine changed. Submit a new analysis with a new request key.",
      });
      return;
    }
    if (!row) {
      // Short-lived analysis state survives restart. Research jobs have separate durable lifecycles.
      db.prepare(
        "DELETE FROM requests WHERE state IN ('completed','failed') AND created<?",
      ).run(Date.now() - 86400000);
      const count = db
        .prepare(
          "SELECT count(*) AS n FROM requests WHERE state IN ('queued','processing')",
        )
        .get().n;
      if (count >= 100) {
        send(res, 503, { error: "Analysis queue full" });
        return;
      }
      const now = Date.now(),
        id = randomUUID();
      db.prepare(
        "INSERT INTO requests(id,request_key,fingerprint,input,state,created,updated,engine_revision) VALUES (?,?,?,?,'queued',?,?,?)",
      ).run(
        id,
        key ?? null,
        fingerprint,
        JSON.stringify(input),
        now,
        now,
        engineRevision,
      );
      row = db.prepare("SELECT * FROM requests WHERE id=?").get(id);
      void pump();
    }
    if (!input.async) {
      const deadline = Date.now() + 20000;
      while (
        Date.now() < deadline &&
        ["queued", "processing"].includes(row.state)
      ) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        row = db.prepare("SELECT * FROM requests WHERE id=?").get(row.id);
      }
    }
    if (row.result) {
      const health = await engine.backendJson("/health");
      if (JSON.parse(row.result).import_id !== health.import_id) {
        send(res, 409, {
          id: row.id,
          status: "stale",
          reason: "Library changed. Submit a new analysis.",
        });
        return;
      }
    }
    if (row.state === "completed") {
      send(res, 200, { ...JSON.parse(row.result), analysis_id: row.id });
      return;
    }
    send(res, row.state === "failed" ? 503 : 202, progress(row));
  } catch (error) {
    console.error(
      JSON.stringify({ event: "request_failed", error: error.message }),
    );
    send(res, 503, { error: "Fact checking temporarily unavailable" });
  }
});
server.listen(Number(process.env.PORT ?? 8081), "0.0.0.0", () =>
  console.log("Fact-ori semantic API listening"),
);
await model.identify(modelPins);
await engine.initialize();
ready = true;
void pump();

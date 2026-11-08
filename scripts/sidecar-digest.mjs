// Detached factori-sorted-json-v1 digests for portable sidecar values.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const CONVENTION = "factori-sorted-json-v1";

function asciiString(value) {
  return JSON.stringify(value).replace(/[\u007f-\uffff]/g, (unit) =>
    `\\u${unit.charCodeAt(0).toString(16).padStart(4, "0")}`);
}

// Python sorts Unicode code points. JavaScript's default sort uses UTF-16 units.
function compareKeys(left, right) {
  const a = Array.from(left, (char) => char.codePointAt(0));
  const b = Array.from(right, (char) => char.codePointAt(0));
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

export function canonicalJson(value) {
  if (value === null || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "string") return asciiString(value);
  if (typeof value === "number" && Number.isSafeInteger(value)) return String(value);
  if (Array.isArray(value)) {
    // Array.from visits holes too, so sparse values fail like undefined fields.
    return `[${Array.from(value, canonicalJson).join(",")}]`;
  }
  if (typeof value === "object" && value !== null &&
      (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null)) {
    if (Reflect.ownKeys(value).length !== Object.keys(value).length) {
      throw new Error("Expected enumerable string object keys");
    }
    return `{${Object.keys(value).sort(compareKeys).map((key) =>
      `${asciiString(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  throw new Error("Expected JSON values with string keys and integers within ±(2^53-1)");
}

export function inspectBytes(raw) {
  const text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(raw);
  // Inspect number tokens before JSON.parse can round a decimal into an integer.
  const tokens = /"(?:[^"\\]|\\.)*"|(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
  for (const match of text.matchAll(tokens)) {
    if (match[1] !== undefined && !/^-?(?:0|[1-9]\d*)$/.test(match[1])) {
      throw new Error("Expected integer JSON number tokens");
    }
  }
  const canonical = canonicalJson(JSON.parse(text));
  const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
  return { canonicalization: CONVENTION, canonical_json: canonical,
    canonical_byte_count: Buffer.byteLength(canonical, "ascii"),
    canonical_sha256: digest(Buffer.from(canonical, "ascii")),
    raw_byte_count: raw.length, raw_sha256: digest(raw) };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    if (process.argv.length !== 3) throw new Error("Usage: node scripts/sidecar-digest.mjs FILE");
    console.log(JSON.stringify(inspectBytes(readFileSync(process.argv[2]))));
  } catch (error) {
    console.error(`sidecar digest failed: ${error.message}`);
    process.exitCode = 2;
  }
}

// Q23 leaf codec. Decoded JSON is UNVALIDATED envelope/result data.
import {Buffer} from 'node:buffer';

export const CHECKPOINT_BYTE_CAP = 262144;
export const CHECKPOINT_MAX_DEPTH = 16;
const contentRejection = Symbol('CHECKPOINT_CONTENT_REJECTION');
const wholeFailure = 'CHECKPOINT_CODEC_FAILURE';
function reject() { throw contentRejection; }
export function isCheckpointContentRejection(error) {
  return error === contentRejection;
}

// Validate encodings explicitly: a decoder's arbitrary exception is not syntax evidence.
function validateUtf8(bytes) {
  for (let i = 0; i < bytes.length;) {
    const a = bytes[i++];
    if (a <= 0x7f) continue;
    let count, low = 0x80, high = 0xbf;
    if (a >= 0xc2 && a <= 0xdf) count = 1;
    else if (a >= 0xe0 && a <= 0xef) {
      count = 2;
      if (a === 0xe0) low = 0xa0;
      if (a === 0xed) high = 0x9f;
    } else if (a >= 0xf0 && a <= 0xf4) {
      count = 3;
      if (a === 0xf0) low = 0x90;
      if (a === 0xf4) high = 0x8f;
    } else reject();
    if (i + count > bytes.length || bytes[i] < low || bytes[i] > high) reject();
    i++;
    for (let j = 1; j < count; j++, i++) {
      if (bytes[i] < 0x80 || bytes[i] > 0xbf) reject();
    }
  }
}

export function parseCheckpointBytesV2(bytes) {
  try {
    if (arguments.length !== 1 || !Buffer.isBuffer(bytes)) throw wholeFailure;
    if (bytes.length > CHECKPOINT_BYTE_CAP) reject();
    validateUtf8(bytes);
    // Buffer decoding retains BOM; JSON whitespace below intentionally excludes it.
    const text = bytes.toString('utf8');
    let i = 0;
    function whitespace() {
      while (text[i] === ' ' || text[i] === '\t' || text[i] === '\r' || text[i] === '\n') i++;
    }
    function string() {
      if (text[i] !== '"') reject();
      const start = i++;
      while (i < text.length) {
        const code = text.charCodeAt(i++);
        if (code === 0x22) {
          // All grammar/escape checks precede conversion; exceptions here are whole failures.
          return JSON.parse(text.slice(start, i));
        }
        if (code < 0x20) reject();
        if (code === 0x5c) {
          const escape = text[i++];
          if (escape === 'u') {
            for (let n = 0; n < 4; n++) {
              const hex = text.charCodeAt(i++);
              if (!((hex >= 48 && hex <= 57) || (hex >= 65 && hex <= 70) || (hex >= 97 && hex <= 102))) reject();
            }
          } else if (!(escape === '"' || escape === '\\' || escape === '/' || escape === 'b' || escape === 'f' || escape === 'n' || escape === 'r' || escape === 't')) reject();
        }
      }
      reject();
    }
    function value(depth) {
      whitespace();
      const c = text[i];
      if (c === '{' || c === '[') {
        // Q15 counts containers: root container is one; scalars do not add depth.
        if (depth >= CHECKPOINT_MAX_DEPTH) reject();
        i++; whitespace();
        if (c === '{') {
          const object = Object.create(null), keys = new Set();
          if (text[i] === '}') { i++; return Object.freeze(object); }
          while (true) {
            whitespace();
            const key = string();
            if (keys.has(key)) reject();
            keys.add(key); whitespace();
            if (text[i++] !== ':') reject();
            const child = value(depth + 1);
            Object.defineProperty(object, key, {value: child, enumerable: true, writable: true, configurable: true});
            whitespace();
            const separator = text[i++];
            if (separator === '}') return Object.freeze(object);
            if (separator !== ',') reject();
          }
        }
        const array = [];
        if (text[i] === ']') { i++; return Object.freeze(array); }
        while (true) {
          array.push(value(depth + 1)); whitespace();
          const separator = text[i++];
          if (separator === ']') return Object.freeze(array);
          if (separator !== ',') reject();
        }
      }
      if (c === '"') return string();
      if (text.startsWith('true', i)) { i += 4; return true; }
      if (text.startsWith('false', i)) { i += 5; return false; }
      if (text.startsWith('null', i)) { i += 4; return null; }
      const number = /-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/y;
      number.lastIndex = i;
      const match = number.exec(text);
      if (!match) reject();
      i = number.lastIndex;
      const result = Number(match[0]);
      if (!Number.isFinite(result)) reject();
      return result;
    }
    const result = value(0);
    whitespace();
    if (i !== text.length) reject();
    return result;
  } catch (error) {
    if (error === contentRejection) throw contentRejection;
    // Fixed primitive has no Error stack/cause/code/name or user-controlled payload.
    throw wholeFailure;
  }
}

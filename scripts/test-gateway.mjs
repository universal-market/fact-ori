// Exercises the actual pinned nginx/config against an isolated echo upstream.
// No Convex database, admin authority, host home/socket or public tunnel involved.
import assert from 'node:assert/strict';
import { request } from 'node:http';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const project = `fact-ori-gateway-test-${process.pid}`;
function compose(...args) {
  const r = spawnSync('docker', ['compose', '--env-file', '/dev/null', '-p', project,
    '-f', 'tests/gateway/compose.yaml', ...args], { cwd: root, encoding: 'utf8', timeout: 90000 });
  if (r.error || r.status !== 0) throw new Error(r.error?.message ?? r.stderr ?? 'Compose failed');
  return r.stdout.trim();
}
function raw(port, path, method = 'GET', body) {
  return new Promise((resolve, reject) => {
    // http.request preserves raw path; URL/fetch would erase literal dot segments.
    const req = request({ hostname: '127.0.0.1', port, path, method, timeout: 5000,
      ...(body ? { headers: { 'Content-Length': Buffer.byteLength(body) } } : {}) }, response => {
      let text = '';
      response.setEncoding('utf8'); response.on('data', chunk => { text += chunk; });
      response.on('end', () => resolve({ status: response.statusCode, text }));
    });
    req.on('error', reject); req.on('timeout', () => req.destroy(new Error('Gateway request timeout')));
    req.end(body);
  });
}
let failures = [];
let checked = 0;
try {
  compose('up', '-d', '--wait', '--wait-timeout', '30');
  const port = Number(compose('port', 'gateway', '8080').split(':').at(-1));
  assert.ok(Number.isSafeInteger(port) && port > 0);
  for (const [path, method] of [
    ['/health', 'GET'], ['/v1/check', 'POST'], ['/v1/check', 'OPTIONS'],
    ['/v1/records/C005?version=1&sha256=abc', 'GET'],
    ['/v1/records/C005?sha256=abc&version=1', 'OPTIONS'],
  ]) {
    const r = await raw(port, path, method); checked++;
    assert.equal(r.status, 200, path);
    assert.equal(JSON.parse(r.text).upstream_path, path);
  }
  for (const [path, method] of [
    ['/v1/jobs/example', 'GET'], ['/api/query', 'POST'], ['/dashboard', 'GET'],
    ['/v1/jobs/..%2F..%2Fhealth', 'GET'], ['/v1/jobs/../../health', 'GET'],
    ['/v1/jobs/..%2f..%2fhealth', 'GET'], ['/v1/jobs/%2e%2e/%2e%2e/health', 'GET'],
    ['/v1/jobs/..%252F..%252Fhealth', 'GET'], ['//health', 'GET'],
    ['/%68ealth', 'GET'], ['/health?extra=1', 'GET'],
    ['/v1/jobs/../../v1/check', 'POST'], ['/v1/jobs/..%2F..%2Fv1/check', 'OPTIONS'],
    ['/v1/jobs/../../v1/records/C005?version=1&sha256=abc', 'GET'],
    ['/v1/jobs/..%2F..%2Fv1/records/C005?version=1&sha256=abc', 'OPTIONS'],
    ['/v1/records/C005?sha256=abc%2Fdef&version=1', 'GET'],
  ]) {
    const r = await raw(port, path, method); checked++;
    if (r.status !== 404 || r.text.includes('upstream_path')) failures.push({ path, method, ...r });
  }
  for (const [path, method] of [['/health', 'POST'], ['/v1/check', 'GET'], ['/v1/records/C005', 'POST']]) {
    const r = await raw(port, path, method); checked++;
    assert.equal(r.status, 403, `${method} ${path}`);
  }
  const large = await raw(port, '/v1/check', 'POST', 'x'.repeat(17000)); checked++;
  assert.equal(large.status, 413);
  if (failures.length) console.error(JSON.stringify({ forbidden_paths_forwarded_or_not_denied: failures }, null, 2));
  assert.equal(failures.length, 0, 'Forbidden raw paths must fail at gateway before upstream');
  console.log(JSON.stringify({ status: 'passed', checks: checked, database_used: false, project }));
} finally {
  // Only this run's disposable containers/network; no persistent volumes exist.
  compose('down', '--timeout', '5');
}

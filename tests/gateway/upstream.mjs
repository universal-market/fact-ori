// Test fixture: echo every raw path so a forwarded forbidden route is observable.
import { createServer } from 'node:http';
const handler=(request, response) => {
  response.writeHead(200, { 'Content-Type': 'application/json' });
  response.end(JSON.stringify({ upstream_path: request.url, method: request.method }));
};
createServer(handler).listen(3211, '0.0.0.0');
createServer(handler).listen(8081, '0.0.0.0');

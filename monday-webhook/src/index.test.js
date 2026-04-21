import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';

process.env.NODE_ENV = 'test';
process.env.PYTHON_BACKEND_URL = 'http://127.0.0.1:1';
process.env.FORWARD_TIMEOUT_MS = '500';

const { app } = await import('./index.js');

let server;
let baseUrl;

before(async () => {
  server = app.listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  const { port } = server.address();
  baseUrl = `http://127.0.0.1:${port}`;
});

after(async () => {
  server.closeAllConnections?.();
  await new Promise((resolve) => server.close(resolve));
});

test('health returns ok', async () => {
  const res = await fetch(`${baseUrl}/health`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, 'ok');
});

test('monday webhook echoes the challenge on handshake', async () => {
  const res = await fetch(`${baseUrl}/webhooks/monday`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ challenge: 'abc123' }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.challenge, 'abc123');
});

test('monday webhook returns 502 when backend is unreachable', async () => {
  // BACKEND is captured at import time and defaults to localhost:8000, which
  // is not running in this test process, so forwarding fails with 502.
  const res = await fetch(`${baseUrl}/webhooks/monday`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ event: { pulseName: 'test', pulseId: 1 } }),
  });
  assert.equal(res.status, 502);
});

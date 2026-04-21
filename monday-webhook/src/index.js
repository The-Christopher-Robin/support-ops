import express from 'express';

const PORT = parseInt(process.env.WEBHOOK_BRIDGE_PORT || '8787', 10);
const BACKEND = process.env.PYTHON_BACKEND_URL || 'http://localhost:8000';
const FORWARD_TIMEOUT_MS = parseInt(process.env.FORWARD_TIMEOUT_MS || '3000', 10);

const app = express();
app.use(express.json({ limit: '1mb' }));

// Monday's webhook handshake: when you first register a webhook they POST a
// { challenge: "..." } body and expect it echoed back.
app.post('/webhooks/monday', async (req, res) => {
  if (req.body && req.body.challenge) {
    return res.json({ challenge: req.body.challenge });
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FORWARD_TIMEOUT_MS);
  try {
    const forward = await fetch(`${BACKEND}/webhooks/monday`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
      signal: controller.signal,
    });
    const text = await forward.text();
    res
      .status(forward.status)
      .type(forward.headers.get('content-type') || 'application/json')
      .send(text);
  } catch (err) {
    console.error('forward failed', err);
    res.status(502).json({ error: 'backend unreachable' });
  } finally {
    clearTimeout(timer);
  }
});

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', backend: BACKEND });
});

if (process.env.NODE_ENV !== 'test') {
  app.listen(PORT, () => {
    console.log(`monday-webhook bridge listening on :${PORT}, forwarding to ${BACKEND}`);
  });
}

export { app };

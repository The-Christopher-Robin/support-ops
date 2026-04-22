# monday-webhook

Small Express service that takes inbound Monday.com webhooks and forwards them
to the Python backend at `/webhooks/monday`. It also handles the initial
challenge handshake Monday uses when registering a webhook.

## Run

```
npm install
PYTHON_BACKEND_URL=http://localhost:8000 npm start
```

Then point your Monday webhook at `http://<host>:8787/webhooks/monday`.

# support-ops

Ticket triage and help-center service. Inbound tickets from Zendesk and
Monday.com land here, get classified by category / priority / sentiment,
matched against an internal knowledge base, and handed back to a human agent
with a draft reply. Urgent items are also escalated to a Monday.com board so
the on-call person sees them without leaving Monday.

## What's in the repo

- `supportops/` — Python package with the FastAPI service, triage pipeline,
  RAG help-center, and Streamlit dashboard.
- `monday-webhook/` — small Express service that receives Monday.com
  webhooks (including the challenge handshake) and forwards them to the
  Python backend.
- `knowledge_base/` — seed help docs across billing, payroll, onboarding,
  and vendor topics. The seeder chunks these, embeds them, and upserts them
  into pgvector (or an in-memory store in mock mode).
- `scripts/` — DB init SQL, knowledge-base seeder, simulator runner.
- `tests/` — unit tests for the triage logic, RAG retrieval, API routes,
  and the Zendesk / Monday clients (mocked with `httpx.MockTransport`).

## Tech stack

- Python 3.10+, FastAPI, SQLAlchemy 2 (async), httpx, tenacity.
- Anthropic Python SDK for triage and help-article drafting.
- OpenAI Python SDK for embeddings (`text-embedding-3-small`).
- LangChain-core for a retriever wrapper around the vector store.
- Postgres 16 with the pgvector extension for the production vector store.
- Streamlit for the operator dashboard.
- Node.js 18+ with Express for the Monday.com webhook bridge.

## Running it locally

The whole stack runs in a "mock mode" out of the box with no external API
keys and no Postgres. Flip `MOCK_MODE=false` in `.env` to talk to real
services.

```bash
# 1. install python deps (editable so local changes reflect immediately)
pip install -e ".[dev]"

# 2. (optional, production mode only) start postgres + pgvector
docker compose up -d db

# 3. seed the knowledge base into the vector store
python scripts/seed_kb.py

# 4. start the API
uvicorn supportops.api.main:app --reload

# 5. (optional) start the dashboard in another shell
streamlit run supportops/dashboard/app.py

# 6. (optional) run the simulator
python scripts/run_simulation.py --tickets 500 --duration 30

# 7. Node.js webhook bridge (optional)
cd monday-webhook && npm install && npm start
```

### Environment

Copy `.env.example` to `.env` and fill in what you need. Relevant knobs:

- `MOCK_MODE` — when true (default), Claude and OpenAI calls are replaced
  with deterministic local stubs so the service runs with zero credentials.
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` — only needed when `MOCK_MODE=false`.
- `DATABASE_URL` — Postgres URL. The supplied docker-compose service matches
  the default value.
- `ZENDESK_*`, `MONDAY_*` — only needed if you want to see actual round-trips
  to those products. The unit tests exercise the clients against fake
  transports either way.

## Architecture

```
[ Zendesk ]  ────(webhook)────┐
                              │
[ Monday.com ] ──(webhook)──► [ monday-webhook (Express) ] ──► [ FastAPI ]
                              │                                     │
[ direct POST /tickets ] ─────┘                                     ▼
                                                            triage pipeline
                                                         (sentiment → priority
                                                           → category → RAG
                                                           → Claude draft)
                                                                    │
                                         ┌──────────────────────────┼──────────┐
                                         ▼                          ▼          ▼
                                    Postgres                  Monday.com   Zendesk
                                  (tickets + KB)             (escalations)  (private
                                                                            comment)
                                         │
                                         ▼
                                     Streamlit
                                     dashboard
```

Every inbound path funnels through `supportops/pipeline.py::ingest`, which is
the single place triage and escalation decisions are made. Webhooks and the
direct API only differ in how they unpack the payload.

## Tests

```
pytest -q
```

Tests are hermetic — they never call Anthropic, OpenAI, or Postgres. Mock
mode is forced on in `tests/conftest.py`, and the Zendesk / Monday clients
are exercised against `httpx.MockTransport` so the HTTP layer is exercised
without a network.

## Scaling notes

- The knowledge base seeds with roughly 20 internal articles for the demo.
  The schema and retrieval path are built to handle 800+ articles without
  changes — the `ivfflat` index on `kb_chunks.embedding` uses 100 lists,
  which is appropriate up to a few hundred thousand chunks.
- The simulator defaults to 1,000 tickets over 60 seconds, which works out
  to the ~1K-tickets-per-day bursts we care about. Bump `--concurrency` to
  push harder.

# Architecture

## One-paragraph summary

A FastAPI service receives tickets from three sources (Zendesk webhooks, a
Node.js Express bridge that forwards Monday.com webhooks, and a direct REST
endpoint used by the simulator and the dashboard). Every ticket funnels
through a single `ingest` function that runs sentiment detection, classifies
the ticket into one of four categories, retrieves grounding snippets from a
pgvector-backed knowledge base, asks Claude to draft a reply, stores the
result, and — for urgent or high-priority items — pushes an item to a
Monday.com PMO board. A Streamlit dashboard polls the service for the
aggregate view.

## Request flow

1. **Inbound.** POST `/tickets` (direct), POST `/webhooks/zendesk`, or POST
   `/webhooks/monday` (via the Express bridge) — all three shapes unpack to
   an `IncomingTicket`.
2. **Persist.** The ticket is inserted via the `TicketStore` abstraction.
   Postgres in production, in-memory in mock mode.
3. **Triage.** `triage.classifier.classify_ticket` asks Claude for a
   (category, priority, sentiment, rationale) JSON object and parses it.
   In mock mode, a keyword heuristic takes the same shape.
4. **Retrieve.** `rag.retriever.Retriever` embeds the ticket text with the
   OpenAI embeddings API and runs a cosine search against `kb_chunks`. The
   retriever is typed as a LangChain `BaseRetriever` so other LangChain
   chains can compose on top of it.
5. **Draft.** `triage.responder.draft_response` calls Claude with the triage
   result and the retrieved snippets, producing a short reviewable draft.
6. **Route.** If the priority is `high` or `urgent`, `integrations.monday`
   creates a Monday.com item so the on-call person sees it there. If the
   ticket originated from Zendesk, `integrations.zendesk` attaches a private
   comment with the triage result.

## Why the two-backend abstraction

`supportops.store` and `supportops.rag.store` both expose a Protocol
(`TicketStore`, `VectorStore`) with an async interface, and ship two
implementations:

- A Postgres-backed one used when `MOCK_MODE=false`.
- An in-memory one used everywhere else.

This lets the test suite exercise the real production code path — the same
`ingest` function, the same retriever — without standing up Postgres. It also
means you can demo the entire system end-to-end with `uvicorn` and nothing
else.

## Failure handling

- Anthropic calls in both `classifier` and `responder` catch `APIError` and
  fall back to the heuristic draft, so a single upstream hiccup never drops
  a ticket on the floor.
- `integrations.zendesk` and `integrations.monday` wrap every call in
  `tenacity` retries with exponential backoff. Three attempts, then raise.
- The Express bridge returns 502 (not 500) when the Python backend is
  unreachable so Monday.com retries the webhook instead of disabling it.

## Scaling notes

- `kb_chunks.embedding` uses an `ivfflat` index with 100 lists, which is
  sized for "hundreds of thousands of rows" territory. Below a couple
  thousand rows the index isn't actually faster than a sequential scan —
  fine to keep it for future-proofing.
- The ticket pipeline is per-request stateless. Horizontal scaling is a
  matter of running more uvicorn workers; all state lives in Postgres.
- The simulator uses poisson-ish jitter so a 1,000-ticket / 60-second run
  produces bursty traffic, not uniform.

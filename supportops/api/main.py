from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from ..config import get_settings
from .tickets import router as tickets_router
from .webhooks import router as webhooks_router


async def _auto_seed_if_mock() -> int:
    """In mock mode each process owns its in-memory vector store, so the API
    needs to seed itself on boot — the offline seeder script writes into a
    different process's memory. In production (pgvector) the seeder populates
    the shared database and this path short-circuits to zero.
    """
    settings = get_settings()
    if not (settings.mock_mode or settings.use_inmemory_store):
        return 0
    from ..rag.embedder import embed_texts
    from ..rag.seed import load_kb
    from ..rag.store import get_store

    docs = load_kb()
    if not docs:
        return 0
    store = get_store()
    embeddings = embed_texts([d.content for d in docs])
    return await store.upsert(docs, embeddings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.started_at = datetime.now(tz=UTC)
    app.state.mock_mode = settings.mock_mode
    app.state.kb_chunks = await _auto_seed_if_mock()
    yield


app = FastAPI(
    title="support-ops",
    version="0.1.0",
    description=(
        "Triage and help-center service for customer support and internal ops tickets."
    ),
    lifespan=lifespan,
)

app.include_router(tickets_router)
app.include_router(webhooks_router)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "mock_mode": app.state.mock_mode,
        "started_at": app.state.started_at.isoformat(),
    }

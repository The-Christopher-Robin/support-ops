from __future__ import annotations

import os

import pytest

# Force mock mode before any supportops module loads settings. This keeps tests
# hermetic: no Claude calls, no OpenAI calls, no Postgres.
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("USE_INMEMORY_STORE", "true")

from supportops.config import get_settings  # noqa: E402
from supportops.rag import store as rag_store  # noqa: E402
from supportops.store import _inmem_tickets  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state():
    get_settings.cache_clear()
    rag_store._inmem_singleton.docs.clear()
    rag_store._inmem_singleton.embeddings.clear()
    _inmem_tickets._rows.clear()
    _inmem_tickets._next_id = 1
    yield

"""Retriever that wraps the vector store in the LangChain retriever protocol.

Exposing this as a LangChain BaseRetriever (even though we call it directly in
most paths) keeps the door open for chaining into LangChain tooling later
without rewriting the store layer.
"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from ..models import RetrievedChunk
from .embedder import embed_texts
from .store import get_store


class Retriever(BaseRetriever):
    """LangChain-compatible retriever backed by our async vector store.

    LangChain's BaseRetriever is sync-first, so we expose `aretrieve` for async
    call sites and let _get_relevant_documents raise to force callers onto the
    async path (matches our FastAPI stack).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    top_k: int = 4
    category: str | None = None
    # Typed as Any because the vector store is a structural Protocol, which
    # pydantic can't express as a field type. We validate it at call time.
    store: Any = None

    def _get_relevant_documents(self, query: str, **kwargs: Any) -> list[Document]:  # noqa: D401
        raise NotImplementedError("use aget_relevant_documents in async contexts")

    async def _aget_relevant_documents(self, query: str, **kwargs: Any) -> list[Document]:
        chunks = await self.aretrieve(query)
        return [
            Document(
                page_content=c.content,
                metadata={
                    "source_path": c.source_path,
                    "title": c.title,
                    "category": c.category,
                    "score": c.score,
                },
            )
            for c in chunks
        ]

    async def aretrieve(self, query: str) -> list[RetrievedChunk]:
        embeddings = embed_texts([query])
        if not embeddings:
            return []
        store = self.store or get_store()
        return await store.search(embeddings[0], top_k=self.top_k, category=self.category)

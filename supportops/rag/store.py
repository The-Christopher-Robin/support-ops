"""Vector store wrapper.

Two backends live here:

* pgvector: production-ish, async, uses the sqlalchemy engine from db.py.
* in-memory: lightweight, used in mock mode and in tests so contributors can
  run the full pipeline with zero infrastructure.

The public surface (upsert / search) is identical so the retriever above this
layer doesn't have to care which backend is wired in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import text

from ..config import get_settings
from ..db import session_scope
from ..models import KBDocument, RetrievedChunk


class VectorStore(Protocol):
    async def upsert(self, docs: list[KBDocument], embeddings: list[list[float]]) -> int: ...
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        category: str | None = None,
    ) -> list[RetrievedChunk]: ...


@dataclass
class InMemoryVectorStore:
    docs: list[KBDocument] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)

    async def upsert(self, docs: list[KBDocument], embeddings: list[list[float]]) -> int:
        for d, e in zip(docs, embeddings, strict=True):
            # replace by source_path if it already exists
            found = False
            for i, existing in enumerate(self.docs):
                if existing.source_path == d.source_path:
                    self.docs[i] = d
                    self.embeddings[i] = e
                    found = True
                    break
            if not found:
                self.docs.append(d)
                self.embeddings.append(e)
        return len(docs)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        category: str | None = None,
    ) -> list[RetrievedChunk]:
        def cosine(a: list[float], b: list[float]) -> float:
            # both are L2-normalized in mock mode, but stay safe anyway.
            dot = sum(x * y for x, y in zip(a, b, strict=True))
            na = sum(x * x for x in a) ** 0.5 or 1.0
            nb = sum(x * x for x in b) ** 0.5 or 1.0
            return dot / (na * nb)

        scored: list[tuple[float, KBDocument]] = []
        for doc, emb in zip(self.docs, self.embeddings, strict=True):
            if category and doc.category != category:
                continue
            scored.append((cosine(query_embedding, emb), doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = scored[:top_k]
        return [
            RetrievedChunk(
                source_path=d.source_path,
                title=d.title,
                category=d.category,
                content=d.content,
                score=score,
            )
            for score, d in top
        ]


class PgvectorStore:
    async def upsert(self, docs: list[KBDocument], embeddings: list[list[float]]) -> int:
        if not docs:
            return 0
        async with session_scope() as session:
            # Delete + insert keeps things simple and idempotent per source_path.
            paths = [d.source_path for d in docs]
            await session.execute(
                text("DELETE FROM kb_chunks WHERE source_path = ANY(:paths)"),
                {"paths": paths},
            )
            params = []
            for d, e in zip(docs, embeddings, strict=True):
                params.append(
                    {
                        "source_path": d.source_path,
                        "title": d.title,
                        "category": d.category,
                        "content": d.content,
                        "embedding": _pgvector_literal(e),
                    }
                )
            await session.execute(
                text(
                    "INSERT INTO kb_chunks (source_path, title, category, content, embedding) "
                    "VALUES (:source_path, :title, :category, :content, CAST(:embedding AS vector))"
                ),
                params,
            )
        return len(docs)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        category: str | None = None,
    ) -> list[RetrievedChunk]:
        where = ""
        params: dict[str, object] = {
            "q": _pgvector_literal(query_embedding),
            "k": top_k,
        }
        if category:
            where = "WHERE category = :category"
            params["category"] = category

        sql = (
            "SELECT source_path, title, category, content, "
            "       1 - (embedding <=> CAST(:q AS vector)) AS score "
            "FROM kb_chunks "
            f"{where} "
            "ORDER BY embedding <=> CAST(:q AS vector) "
            "LIMIT :k"
        )
        async with session_scope() as session:
            rows = (await session.execute(text(sql), params)).mappings().all()
        return [
            RetrievedChunk(
                source_path=r["source_path"],
                title=r["title"],
                category=r["category"],
                content=r["content"],
                score=float(r["score"]),
            )
            for r in rows
        ]


def _pgvector_literal(vec: list[float]) -> str:
    # pgvector accepts a plain "[1,2,3]" string for its vector literal syntax.
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


_inmem_singleton = InMemoryVectorStore()


def get_store() -> VectorStore:
    settings = get_settings()
    if settings.mock_mode or settings.use_inmemory_store:
        return _inmem_singleton
    return PgvectorStore()

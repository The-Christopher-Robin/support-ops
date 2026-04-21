"""Embedding generation.

Uses OpenAI's text-embedding-3-small in production. In mock mode the embedding
is a deterministic hashed bag-of-words vector of the configured dimensionality
so every unit downstream (cosine math, pgvector column size, retriever scoring)
behaves the same shape-wise.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import TYPE_CHECKING

from ..config import get_settings

if TYPE_CHECKING:
    from openai import OpenAI


EMBEDDING_DIM = 1536

_STOPWORDS = frozenset(
    """a an and the is are was were be been being of to for on in at by with
    from as it its this that these those i you we they he she how do does did
    can could should would will what when where which who whom whose or but not
    if then so than too very just my your our their his her about over under
    into onto out up down off here there""".split()
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9-]+")


def _hash_embed(text: str) -> list[float]:
    """Deterministic pseudo-embedding used only in mock mode.

    Not semantic, but good enough for the mock pipeline to be demo-able and
    for tests to verify that keyword-overlapping docs rank above unrelated
    docs. We filter stopwords before hashing so short-query / short-doc
    overlaps don't drown in "a the and" collisions.
    """
    vec = [0.0] * EMBEDDING_DIM
    tokens = [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS]
    if not tokens:
        return vec
    for tok in tokens:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        # 4 bytes per slot, 4 slots per token. Enough spread to keep unrelated
        # tokens mostly orthogonal while letting shared tokens align.
        for i in range(0, 16, 4):
            idx = int.from_bytes(h[i : i + 4], "big") % EMBEDDING_DIM
            vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _openai_client() -> OpenAI:
    from openai import OpenAI

    return OpenAI(api_key=get_settings().openai_api_key)


def embed_texts(texts: list[str], *, client: "OpenAI | None" = None) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    if settings.mock_mode:
        return [_hash_embed(t) for t in texts]

    client = client or _openai_client()
    resp = client.embeddings.create(model=settings.embedding_model, input=texts)
    return [item.embedding for item in resp.data]

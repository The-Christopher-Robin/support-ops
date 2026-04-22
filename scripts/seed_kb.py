"""Walk the knowledge_base/ tree and upsert every chunk into the configured
vector store (pgvector in production, in-memory in mock mode).

Usage:
    python scripts/seed_kb.py
    MOCK_MODE=false python scripts/seed_kb.py
"""

from __future__ import annotations

import argparse
import asyncio

from rich.console import Console

from supportops.rag.embedder import embed_texts
from supportops.rag.seed import KB_ROOT, load_kb
from supportops.rag.store import get_store


console = Console()


async def main(batch_size: int) -> None:
    docs = load_kb()
    if not docs:
        console.print("[red]No docs found under knowledge_base/. Nothing to seed.[/red]")
        return
    console.print(f"Loaded [bold]{len(docs)}[/bold] chunks from {KB_ROOT}")

    store = get_store()
    total = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        embeddings = embed_texts([d.content for d in batch])
        inserted = await store.upsert(batch, embeddings)
        total += inserted
        console.print(f"  upserted {inserted} (running total: {total})")
    console.print(f"[green]done. {total} chunks indexed.[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    asyncio.run(main(args.batch_size))

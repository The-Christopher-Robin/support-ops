"""Help-center Q&A over the knowledge base.

Given a user question we:

1. retrieve the top-k snippets from the vector store (optionally scoped by
   category to cut noise when we already know what the ticket is about);
2. compose a grounded prompt and ask Claude for a short answer that cites the
   snippet paths; or
3. if we're in mock mode, return the highest-scoring snippet verbatim so the
   demo path still produces something readable.
"""

from __future__ import annotations

from dataclasses import dataclass

from anthropic import APIError

from ..config import get_settings
from ..models import Category, RetrievedChunk
from .retriever import Retriever


@dataclass
class HelpAnswer:
    answer: str
    retrieved: list[RetrievedChunk]


_SYSTEM_PROMPT = (
    "You are an internal help-center assistant. Answer ONLY from the provided snippets. "
    "If the snippets do not contain the answer, say you don't have the answer and suggest "
    "opening a ticket. Cite source_path at the end on a line starting with 'Sources:'."
)


async def answer_question(
    question: str,
    *,
    category: Category | None = None,
    top_k: int = 4,
) -> HelpAnswer:
    retriever = Retriever(top_k=top_k, category=category)
    chunks = await retriever.aretrieve(question)
    settings = get_settings()
    if not chunks:
        return HelpAnswer(
            answer="I don't have a confident answer in the knowledge base. Opening a ticket.",
            retrieved=[],
        )

    if settings.mock_mode:
        top = chunks[0]
        answer = f"{top.content.strip()}\n\nSources: {top.source_path}"
        return HelpAnswer(answer=answer, retrieved=chunks)

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)
        snippets = "\n\n".join(
            f"[{i + 1}] {c.source_path}\n{c.content}" for i, c in enumerate(chunks)
        )
        resp = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=500,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nSnippets:\n{snippets}",
                }
            ],
        )
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        ).strip()
        return HelpAnswer(answer=text, retrieved=chunks)
    except APIError as exc:
        top = chunks[0]
        fallback = (
            f"(fallback due to upstream error: {exc})\n\n{top.content.strip()}"
            f"\n\nSources: {top.source_path}"
        )
        return HelpAnswer(answer=fallback, retrieved=chunks)

from __future__ import annotations

import pytest

from supportops.models import KBDocument
from supportops.rag.embedder import embed_texts
from supportops.rag.help_center import answer_question
from supportops.rag.retriever import Retriever
from supportops.rag.store import get_store


@pytest.fixture
async def seeded_store():
    docs = [
        KBDocument(
            source_path="billing/refund-policy.md",
            title="Refund policy",
            category="billing",
            content="We issue refunds within 30 days of the original invoice charge.",
        ),
        KBDocument(
            source_path="payroll/direct-deposit.md",
            title="Direct deposit setup",
            category="payroll",
            content="Direct deposit enrollment requires a voided check or ABA routing number.",
        ),
        KBDocument(
            source_path="onboarding/first-login.md",
            title="First login troubleshooting",
            category="onboarding",
            content="If first login fails, confirm MFA enrollment and browser cookies are enabled.",
        ),
        KBDocument(
            source_path="vendor/partner-integration.md",
            title="Vendor integrations",
            category="vendor",
            content="Vendor integration errors are usually a rotated API token or stale webhook URL.",
        ),
    ]
    store = get_store()
    embeddings = embed_texts([d.content for d in docs])
    await store.upsert(docs, embeddings)
    return store


async def test_retriever_returns_relevant_category(seeded_store):
    retriever = Retriever(top_k=2)
    chunks = await retriever.aretrieve("How do I get a refund on an invoice?")
    assert chunks, "retriever should return at least one hit"
    assert chunks[0].category == "billing"


async def test_retriever_category_filter(seeded_store):
    retriever = Retriever(top_k=5, category="payroll")
    chunks = await retriever.aretrieve("direct deposit routing")
    assert chunks
    assert {c.category for c in chunks} == {"payroll"}


async def test_help_center_mock_mode_cites_source(seeded_store):
    answer = await answer_question("How do I fix first login?", category="onboarding")
    assert answer.retrieved
    assert "Sources:" in answer.answer
    assert any("first-login" in c.source_path for c in answer.retrieved)


async def test_empty_store_returns_fallback_answer():
    answer = await answer_question("anything at all")
    assert answer.retrieved == []
    assert "ticket" in answer.answer.lower()

from __future__ import annotations

import pytest

from supportops.models import IncomingTicket, KBDocument, TicketSource
from supportops.pipeline import ingest
from supportops.rag.embedder import embed_texts
from supportops.rag.store import get_store


@pytest.fixture(autouse=True)
async def _seed_kb():
    store = get_store()
    docs = [
        KBDocument(
            source_path="billing/refunds.md",
            title="Refund policy",
            category="billing",
            content="We issue refunds within 30 days. Attach the invoice number to speed things up.",
        ),
        KBDocument(
            source_path="payroll/deposit.md",
            title="Direct deposit",
            category="payroll",
            content="Direct deposit requires a voided check and takes two pay cycles to take effect.",
        ),
    ]
    embeddings = embed_texts([d.content for d in docs])
    await store.upsert(docs, embeddings)


async def test_ingest_end_to_end_billing_ticket():
    ticket = IncomingTicket(
        source=TicketSource.DIRECT,
        subject="Refund on last invoice",
        body="Hi, I was double charged on my credit card for invoice 8811.",
    )
    outcome = await ingest(ticket)

    assert outcome.ticket.id > 0
    assert outcome.ticket.status == "triaged"
    assert outcome.triage.category == "billing"
    assert outcome.draft.text
    assert "billing" in outcome.draft.text.lower() or "invoice" in outcome.draft.text.lower()


async def test_ingest_escalates_urgent_to_monday():
    ticket = IncomingTicket(
        source=TicketSource.DIRECT,
        subject="Payroll broken — production blocker",
        body="URGENT: direct deposit failed for the whole team, we are blocked in production.",
    )
    outcome = await ingest(ticket)

    assert outcome.triage.priority == "urgent"
    assert outcome.monday_item is not None
    assert outcome.monday_item.get("mock") is True

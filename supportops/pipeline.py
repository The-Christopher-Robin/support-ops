"""End-to-end intake pipeline.

Anything entering the system (direct API, Zendesk webhook, Monday.com webhook)
goes through this single function so triage logic isn't scattered across
callers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .integrations import MondayClient, ZendeskClient
from .models import DraftResponse, IncomingTicket, Ticket, TriageResult
from .rag.retriever import Retriever
from .store import get_ticket_store
from .triage import classify_ticket, draft_response


log = logging.getLogger(__name__)


@dataclass
class TriageOutcome:
    ticket: Ticket
    triage: TriageResult
    draft: DraftResponse
    monday_item: dict | None


async def ingest(ticket: IncomingTicket) -> TriageOutcome:
    store = get_ticket_store()
    row = await store.create(ticket)

    triage = classify_ticket(ticket)

    retriever = Retriever(top_k=3, category=triage.category if triage.category != "other" else None)
    chunks = await retriever.aretrieve(f"{ticket.subject}\n{ticket.body}")

    draft = draft_response(ticket, triage, chunks)

    row = await store.mark_triaged(
        row.id,
        category=triage.category,
        priority=triage.priority,
        sentiment=triage.sentiment,
        draft_response=draft.text,
    )

    monday_item: dict | None = None
    if triage.priority in ("high", "urgent"):
        monday = MondayClient()
        monday_item = await monday.create_task(
            title=f"[{triage.category}] {ticket.subject}"[:255],
            description=ticket.body,
            priority=triage.priority,
            category=triage.category,
        )

    if ticket.external_id and ticket.source.value == "zendesk":
        zd = ZendeskClient()
        await zd.add_private_comment(
            ticket.external_id,
            body=(
                f"Triage -> category={triage.category}, priority={triage.priority}, "
                f"sentiment={triage.sentiment}.\n\nDraft reply:\n{draft.text}"
            ),
        )

    log.info(
        "triaged ticket id=%s source=%s category=%s priority=%s sentiment=%s retrieved=%d escalated=%s",
        row.id,
        ticket.source.value,
        triage.category,
        triage.priority,
        triage.sentiment,
        len(chunks),
        monday_item is not None,
    )
    return TriageOutcome(ticket=row, triage=triage, draft=draft, monday_item=monday_item)

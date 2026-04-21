"""Webhook receivers.

These endpoints turn inbound events from Zendesk (new ticket / comment) and
Monday.com (new item on the escalations board) into normalized IncomingTicket
records and push them through the standard intake pipeline.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..models import IncomingTicket, TicketSource
from ..pipeline import ingest

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/zendesk")
async def zendesk_webhook(request: Request) -> dict[str, Any]:
    payload = await request.json()
    # Zendesk's "ticket.created" payload puts everything under "ticket".
    t = payload.get("ticket") or payload
    ticket = IncomingTicket(
        external_id=str(t.get("id") or t.get("ticket_id") or ""),
        source=TicketSource.ZENDESK,
        subject=t.get("subject") or t.get("title") or "(no subject)",
        body=t.get("description") or t.get("body") or "",
        requester_email=_pull_email(t),
    )
    outcome = await ingest(ticket)
    return {
        "ticket_id": outcome.ticket.id,
        "category": outcome.triage.category,
        "priority": outcome.triage.priority,
        "escalated_to_monday": outcome.monday_item is not None,
    }


@router.post("/monday")
async def monday_webhook(request: Request) -> dict[str, Any]:
    payload = await request.json()
    event = payload.get("event") or payload
    pulse = event.get("pulseName") or event.get("name") or "(no title)"
    body = event.get("text") or event.get("value") or ""
    ticket = IncomingTicket(
        external_id=str(event.get("pulseId") or event.get("itemId") or ""),
        source=TicketSource.MONDAY,
        subject=pulse,
        body=body or pulse,
    )
    outcome = await ingest(ticket)
    return {
        "ticket_id": outcome.ticket.id,
        "category": outcome.triage.category,
        "priority": outcome.triage.priority,
    }


def _pull_email(t: dict[str, Any]) -> str | None:
    requester = t.get("requester") or {}
    if isinstance(requester, dict):
        return requester.get("email") or requester.get("address")
    return t.get("requester_email")

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models import DraftResponse, IncomingTicket, Ticket, TriageResult
from ..pipeline import ingest
from ..rag.help_center import answer_question
from ..store import get_ticket_store

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TriageResponse(BaseModel):
    ticket: Ticket
    triage: TriageResult
    draft: DraftResponse
    escalated_to_monday: bool


@router.post("", response_model=TriageResponse)
async def create_ticket(payload: IncomingTicket) -> TriageResponse:
    outcome = await ingest(payload)
    return TriageResponse(
        ticket=outcome.ticket,
        triage=outcome.triage,
        draft=outcome.draft,
        escalated_to_monday=outcome.monday_item is not None,
    )


@router.get("", response_model=list[Ticket])
async def list_tickets(limit: int = 100) -> list[Ticket]:
    store = get_ticket_store()
    return await store.list_recent(limit=limit)


@router.get("/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: int) -> Ticket:
    store = get_ticket_store()
    row = await store.get(ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="ticket not found")
    return row


@router.post("/{ticket_id}/resolve", response_model=Ticket)
async def resolve_ticket(ticket_id: int) -> Ticket:
    store = get_ticket_store()
    try:
        return await store.mark_resolved(ticket_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ticket not found") from exc


class HelpQuery(BaseModel):
    question: str
    category: str | None = None
    top_k: int = 4


@router.post("/help")
async def ask_help_center(payload: HelpQuery) -> dict:
    result = await answer_question(
        payload.question,
        category=payload.category,  # type: ignore[arg-type]
        top_k=payload.top_k,
    )
    return {
        "answer": result.answer,
        "retrieved": [c.model_dump() for c in result.retrieved],
    }

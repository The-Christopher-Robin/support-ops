from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


Category = Literal["billing", "payroll", "onboarding", "vendor", "other"]
Priority = Literal["low", "medium", "high", "urgent"]
Sentiment = Literal["positive", "neutral", "negative", "frustrated"]


class TicketSource(str, Enum):
    ZENDESK = "zendesk"
    MONDAY = "monday"
    DIRECT = "direct"


class IncomingTicket(BaseModel):
    """Payload shape accepted by POST /tickets and the webhook routes."""

    external_id: str | None = None
    source: TicketSource = TicketSource.DIRECT
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    requester_email: EmailStr | None = None


class TriageResult(BaseModel):
    category: Category
    priority: Priority
    sentiment: Sentiment
    rationale: str = ""


class DraftResponse(BaseModel):
    text: str
    cited_sources: list[str] = Field(default_factory=list)


class Ticket(BaseModel):
    id: int
    external_id: str | None
    source: TicketSource
    subject: str
    body: str
    requester_email: str | None
    category: Category | None
    priority: Priority | None
    sentiment: Sentiment | None
    status: str
    draft_response: str | None
    created_at: datetime
    triaged_at: datetime | None
    resolved_at: datetime | None


class KBDocument(BaseModel):
    source_path: str
    title: str
    category: Category
    content: str


class RetrievedChunk(BaseModel):
    source_path: str
    title: str
    category: Category
    content: str
    score: float

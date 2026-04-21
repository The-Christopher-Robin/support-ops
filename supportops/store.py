"""Ticket persistence.

Mirrors the two-backend approach used for the vector store: an in-memory list
(used in mock_mode and tests) and a Postgres-backed implementation that speaks
SQLAlchemy. The in-memory backend is a plain list wrapped in an asyncio lock
so the simulator can pound on it from many coroutines without corrupting state.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select, update

from .config import get_settings
from .db import TicketRow, session_scope
from .models import (
    Category,
    IncomingTicket,
    Priority,
    Sentiment,
    Ticket,
    TicketSource,
)


class TicketStore(Protocol):
    async def create(self, ticket: IncomingTicket) -> Ticket: ...
    async def mark_triaged(
        self,
        ticket_id: int,
        category: Category,
        priority: Priority,
        sentiment: Sentiment,
        draft_response: str,
    ) -> Ticket: ...
    async def mark_resolved(self, ticket_id: int) -> Ticket: ...
    async def list_recent(self, limit: int = 100) -> list[Ticket]: ...
    async def get(self, ticket_id: int) -> Ticket | None: ...


@dataclass
class InMemoryTicketStore:
    _rows: list[Ticket] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _next_id: int = 1

    async def create(self, ticket: IncomingTicket) -> Ticket:
        async with self._lock:
            row = Ticket(
                id=self._next_id,
                external_id=ticket.external_id,
                source=ticket.source,
                subject=ticket.subject,
                body=ticket.body,
                requester_email=ticket.requester_email,
                category=None,
                priority=None,
                sentiment=None,
                status="open",
                draft_response=None,
                created_at=datetime.now(tz=UTC),
                triaged_at=None,
                resolved_at=None,
            )
            self._rows.append(row)
            self._next_id += 1
            return row

    async def mark_triaged(
        self,
        ticket_id: int,
        category: Category,
        priority: Priority,
        sentiment: Sentiment,
        draft_response: str,
    ) -> Ticket:
        async with self._lock:
            for i, row in enumerate(self._rows):
                if row.id == ticket_id:
                    updated = row.model_copy(
                        update={
                            "category": category,
                            "priority": priority,
                            "sentiment": sentiment,
                            "draft_response": draft_response,
                            "triaged_at": datetime.now(tz=UTC),
                            "status": "triaged",
                        }
                    )
                    self._rows[i] = updated
                    return updated
        raise KeyError(ticket_id)

    async def mark_resolved(self, ticket_id: int) -> Ticket:
        async with self._lock:
            for i, row in enumerate(self._rows):
                if row.id == ticket_id:
                    updated = row.model_copy(
                        update={"status": "resolved", "resolved_at": datetime.now(tz=UTC)}
                    )
                    self._rows[i] = updated
                    return updated
        raise KeyError(ticket_id)

    async def list_recent(self, limit: int = 100) -> list[Ticket]:
        async with self._lock:
            return sorted(self._rows, key=lambda r: r.created_at, reverse=True)[:limit]

    async def get(self, ticket_id: int) -> Ticket | None:
        async with self._lock:
            for row in self._rows:
                if row.id == ticket_id:
                    return row
            return None


class PgTicketStore:
    @staticmethod
    def _to_ticket(row: TicketRow) -> Ticket:
        return Ticket(
            id=row.id,
            external_id=row.external_id,
            source=TicketSource(row.source),
            subject=row.subject,
            body=row.body,
            requester_email=row.requester_email,
            category=row.category,  # type: ignore[arg-type]
            priority=row.priority,  # type: ignore[arg-type]
            sentiment=row.sentiment,  # type: ignore[arg-type]
            status=row.status,
            draft_response=row.draft_response,
            created_at=row.created_at,
            triaged_at=row.triaged_at,
            resolved_at=row.resolved_at,
        )

    async def create(self, ticket: IncomingTicket) -> Ticket:
        async with session_scope() as session:
            row = TicketRow(
                external_id=ticket.external_id,
                source=ticket.source.value,
                subject=ticket.subject,
                body=ticket.body,
                requester_email=ticket.requester_email,
                status="open",
            )
            session.add(row)
            await session.flush()
            return self._to_ticket(row)

    async def mark_triaged(
        self,
        ticket_id: int,
        category: Category,
        priority: Priority,
        sentiment: Sentiment,
        draft_response: str,
    ) -> Ticket:
        async with session_scope() as session:
            await session.execute(
                update(TicketRow)
                .where(TicketRow.id == ticket_id)
                .values(
                    category=category,
                    priority=priority,
                    sentiment=sentiment,
                    draft_response=draft_response,
                    triaged_at=datetime.now(tz=UTC),
                    status="triaged",
                )
            )
            row = (
                await session.execute(select(TicketRow).where(TicketRow.id == ticket_id))
            ).scalar_one()
            return self._to_ticket(row)

    async def mark_resolved(self, ticket_id: int) -> Ticket:
        async with session_scope() as session:
            await session.execute(
                update(TicketRow)
                .where(TicketRow.id == ticket_id)
                .values(status="resolved", resolved_at=datetime.now(tz=UTC))
            )
            row = (
                await session.execute(select(TicketRow).where(TicketRow.id == ticket_id))
            ).scalar_one()
            return self._to_ticket(row)

    async def list_recent(self, limit: int = 100) -> list[Ticket]:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(TicketRow).order_by(TicketRow.created_at.desc()).limit(limit)
                )
            ).scalars().all()
            return [self._to_ticket(r) for r in rows]

    async def get(self, ticket_id: int) -> Ticket | None:
        async with session_scope() as session:
            row = (
                await session.execute(select(TicketRow).where(TicketRow.id == ticket_id))
            ).scalar_one_or_none()
            return self._to_ticket(row) if row else None


_inmem_tickets = InMemoryTicketStore()


def get_ticket_store() -> TicketStore:
    settings = get_settings()
    if settings.mock_mode or settings.use_inmemory_store:
        return _inmem_tickets
    return PgTicketStore()

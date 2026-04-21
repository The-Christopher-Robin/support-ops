"""Thin async Zendesk client.

Only the endpoints we actually exercise (fetch tickets, comment on a ticket,
move ticket status) are implemented. Keeps the surface small so the mock mode
equivalent is obvious.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..models import IncomingTicket, TicketSource


class ZendeskClient:
    def __init__(
        self,
        subdomain: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        s = get_settings()
        self.subdomain = subdomain or s.zendesk_subdomain
        self.email = email or s.zendesk_email
        self.api_token = api_token or s.zendesk_api_token
        self._base = f"https://{self.subdomain}.zendesk.com/api/v2"
        self._transport = transport

    def _auth_header(self) -> dict[str, str]:
        token = f"{self.email}/token:{self.api_token}".encode()
        return {"Authorization": "Basic " + base64.b64encode(token).decode()}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self._auth_header(),
            timeout=httpx.Timeout(10.0, connect=5.0),
            transport=self._transport,
        )

    @retry(wait=wait_exponential(multiplier=0.5, max=4), stop=stop_after_attempt(3), reraise=True)
    async def list_open_tickets(self, limit: int = 100) -> list[IncomingTicket]:
        if get_settings().mock_mode:
            return []
        async with self._client() as cx:
            r = await cx.get(f"{self._base}/tickets.json", params={"per_page": limit})
            r.raise_for_status()
            data = r.json().get("tickets", [])
        return [
            IncomingTicket(
                external_id=str(t["id"]),
                source=TicketSource.ZENDESK,
                subject=t.get("subject", ""),
                body=t.get("description", ""),
                requester_email=(t.get("via", {}).get("source", {}).get("from", {}).get("address")),
            )
            for t in data
        ]

    @retry(wait=wait_exponential(multiplier=0.5, max=4), stop=stop_after_attempt(3), reraise=True)
    async def add_private_comment(self, ticket_id: str, body: str) -> dict[str, Any]:
        if get_settings().mock_mode:
            return {"mock": True, "ticket_id": ticket_id, "body": body}
        payload = {"ticket": {"comment": {"body": body, "public": False}}}
        async with self._client() as cx:
            r = await cx.put(f"{self._base}/tickets/{ticket_id}.json", json=payload)
            r.raise_for_status()
            return r.json()

    @retry(wait=wait_exponential(multiplier=0.5, max=4), stop=stop_after_attempt(3), reraise=True)
    async def set_priority(self, ticket_id: str, priority: str) -> dict[str, Any]:
        if get_settings().mock_mode:
            return {"mock": True, "ticket_id": ticket_id, "priority": priority}
        payload = {"ticket": {"priority": priority}}
        async with self._client() as cx:
            r = await cx.put(f"{self._base}/tickets/{ticket_id}.json", json=payload)
            r.raise_for_status()
            return r.json()

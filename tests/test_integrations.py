from __future__ import annotations

import httpx
import pytest

from supportops.config import get_settings
from supportops.integrations import MondayClient, ZendeskClient
from supportops.models import TicketSource


async def test_zendesk_client_mock_mode_is_noop():
    assert get_settings().mock_mode is True
    zd = ZendeskClient(subdomain="example", email="a@b.co", api_token="x")
    # In mock mode these return stub dicts without making network calls.
    result = await zd.add_private_comment("123", "hello")
    assert result == {"mock": True, "ticket_id": "123", "body": "hello"}

    tickets = await zd.list_open_tickets()
    assert tickets == []


async def test_zendesk_client_against_mock_transport(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "false")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/tickets.json"):
            return httpx.Response(
                200,
                json={
                    "tickets": [
                        {
                            "id": 42,
                            "subject": "Refund on invoice",
                            "description": "I was charged twice.",
                            "via": {"source": {"from": {"address": "ann@example.com"}}},
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    zd = ZendeskClient(
        subdomain="example", email="a@b.co", api_token="x", transport=transport
    )
    tickets = await zd.list_open_tickets()
    assert len(tickets) == 1
    assert tickets[0].source == TicketSource.ZENDESK
    assert tickets[0].external_id == "42"
    assert tickets[0].requester_email == "ann@example.com"

    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()


async def test_monday_client_mock_mode():
    m = MondayClient(api_token="x", board_id="1")
    out = await m.create_task(
        title="Urgent payroll escalation",
        description="Direct deposit failed for 12 employees",
        priority="urgent",
        category="payroll",
    )
    assert out["mock"] is True
    assert out["priority"] == "urgent"
    assert out["category"] == "payroll"


async def test_monday_client_graphql_error_surfaces(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "false")
    get_settings.cache_clear()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "bad token"}]})

    transport = httpx.MockTransport(handler)
    m = MondayClient(api_token="bad", board_id="1", transport=transport)
    with pytest.raises(RuntimeError, match="monday API returned errors"):
        await m.create_task(
            title="t",
            description="d",
            priority="high",
            category="billing",
        )

    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()

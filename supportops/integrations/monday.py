"""Monday.com client used to push escalations onto a PMO board.

Monday's API is GraphQL but we wrap the specific mutations we care about in
small Python helpers so callers don't have to hand-roll GraphQL.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..models import Priority


_MONDAY_API = "https://api.monday.com/v2"


class MondayClient:
    def __init__(
        self,
        api_token: str | None = None,
        board_id: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        s = get_settings()
        self.api_token = api_token or s.monday_api_token
        self.board_id = board_id or s.monday_board_id
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": "2024-01",
        }
        return httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(10.0, connect=5.0),
            transport=self._transport,
        )

    @retry(wait=wait_exponential(multiplier=0.5, max=4), stop=stop_after_attempt(3), reraise=True)
    async def create_task(
        self,
        title: str,
        description: str,
        priority: Priority,
        category: str,
    ) -> dict[str, Any]:
        if get_settings().mock_mode:
            return {
                "mock": True,
                "title": title,
                "priority": priority,
                "category": category,
                "description_len": len(description),
            }

        column_values = json.dumps(
            {
                "text": description[:400],
                "priority": {"label": priority.capitalize()},
                "category": {"label": category},
            }
        )
        query = (
            "mutation ($board: ID!, $name: String!, $values: JSON!) { "
            "create_item(board_id: $board, item_name: $name, column_values: $values) "
            "{ id name } }"
        )
        async with self._client() as cx:
            r = await cx.post(
                _MONDAY_API,
                json={
                    "query": query,
                    "variables": {"board": self.board_id, "name": title, "values": column_values},
                },
            )
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
                raise RuntimeError(f"monday API returned errors: {data['errors']}")
            return data.get("data", {}).get("create_item", {})

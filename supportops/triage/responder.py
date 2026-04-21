"""Auto-response drafter.

Given a triaged ticket and a handful of retrieved knowledge-base chunks this
module produces a draft reply for a human agent to review. In mock mode the
draft is assembled from a small template library so the pipeline still produces
something demo-able and deterministic for tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anthropic import APIError

from ..config import get_settings
from ..models import DraftResponse, IncomingTicket, RetrievedChunk, TriageResult
from .prompts import RESPONSE_SYSTEM, RESPONSE_USER_TEMPLATE

if TYPE_CHECKING:
    from anthropic import Anthropic


_MOCK_TEMPLATES = {
    "billing": (
        "Thanks for flagging this billing question. I've pulled up the invoice on our side and "
        "will walk you through the charges in my next reply. If anything looks off after that, "
        "we can open a refund request in the same thread."
    ),
    "payroll": (
        "Thanks for the details on the payroll issue. I'm looping in our payroll specialist now "
        "and confirming the pay-period and direct-deposit details so we can resolve this in the "
        "current cycle."
    ),
    "onboarding": (
        "Welcome aboard. I'll send over the setup checklist and make sure your first-login flow "
        "is unblocked. If you can share a screenshot of where you're stuck, I can jump straight "
        "to that step."
    ),
    "vendor": (
        "Thanks for the heads up on the vendor integration. I'll reach out to the partner team "
        "with the trace ID from your message and come back here with next steps as soon as I "
        "hear back."
    ),
    "other": (
        "Thanks for reaching out. I'm assigning this to the right team and will follow up here "
        "with a concrete next step shortly."
    ),
}


def _mock_draft(
    ticket: IncomingTicket,
    triage: TriageResult,
    chunks: list[RetrievedChunk],
) -> DraftResponse:
    base = _MOCK_TEMPLATES.get(triage.category, _MOCK_TEMPLATES["other"])
    cited = [c.source_path for c in chunks[:2]]
    if cited:
        base = base + "\n\nSources: " + ", ".join(cited)
    return DraftResponse(text=base, cited_sources=cited)


def _format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no relevant snippets retrieved)"
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(f"[{i}] {c.source_path} (score={c.score:.3f})\n{c.content.strip()}")
    return "\n\n".join(lines)


def _get_client() -> Anthropic:
    from anthropic import Anthropic

    return Anthropic(api_key=get_settings().anthropic_api_key)


def draft_response(
    ticket: IncomingTicket,
    triage: TriageResult,
    chunks: list[RetrievedChunk],
    *,
    client: "Anthropic | None" = None,
) -> DraftResponse:
    settings = get_settings()
    if settings.mock_mode:
        return _mock_draft(ticket, triage, chunks)

    client = client or _get_client()
    user = RESPONSE_USER_TEMPLATE.format(
        category=triage.category,
        priority=triage.priority,
        sentiment=triage.sentiment,
        subject=ticket.subject,
        body=ticket.body,
        context=_format_context(chunks),
    )
    try:
        resp = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=400,
            system=RESPONSE_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        return DraftResponse(text=text, cited_sources=[c.source_path for c in chunks[:3]])
    except APIError as exc:
        mock = _mock_draft(ticket, triage, chunks)
        mock.text = f"(fallback due to upstream error: {exc})\n\n" + mock.text
        return mock

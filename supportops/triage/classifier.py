"""Ticket classifier.

Uses the Anthropic messages API in production and a deterministic keyword/regex
heuristic in mock mode so the rest of the stack (and the test suite) can run
without an API key. The heuristic is intentionally small but covers the four
categories the internal ops team actually cares about.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from anthropic import APIError

from ..config import get_settings
from ..models import Category, IncomingTicket, Priority, Sentiment, TriageResult
from .prompts import TRIAGE_SYSTEM, TRIAGE_USER_TEMPLATE
from .sentiment import detect_sentiment

if TYPE_CHECKING:
    from anthropic import Anthropic


CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    "billing": ("invoice", "charge", "refund", "billing", "payment", "credit card", "receipt"),
    "payroll": ("payroll", "paycheck", "w-2", "w2", "wages", "direct deposit", "paystub"),
    "onboarding": ("onboard", "setup", "getting started", "first login", "migration", "import"),
    "vendor": ("vendor", "supplier", "third party", "partner", "integration partner"),
}

URGENT_MARKERS = ("urgent", "asap", "immediately", "production down", "can't access", "blocked")


def _heuristic_category(subject: str, body: str) -> Category:
    haystack = f"{subject}\n{body}".lower()
    scores: dict[Category, int] = {c: 0 for c in CATEGORY_KEYWORDS}
    for cat, terms in CATEGORY_KEYWORDS.items():
        for term in terms:
            if term in haystack:
                scores[cat] += 1
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0 else "other"


def _heuristic_priority(subject: str, body: str, sentiment: Sentiment) -> Priority:
    haystack = f"{subject}\n{body}".lower()
    if any(m in haystack for m in URGENT_MARKERS):
        return "urgent"
    if sentiment == "frustrated":
        return "high"
    if sentiment == "negative":
        return "medium"
    return "low"


def _heuristic_triage(ticket: IncomingTicket) -> TriageResult:
    sentiment = detect_sentiment(ticket.body)
    category = _heuristic_category(ticket.subject, ticket.body)
    priority = _heuristic_priority(ticket.subject, ticket.body, sentiment)
    return TriageResult(
        category=category,
        priority=priority,
        sentiment=sentiment,
        rationale=f"Matched keyword scan for category={category}; priority set by urgency markers and sentiment.",
    )


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_triage_json(raw: str) -> TriageResult:
    m = _JSON_BLOCK.search(raw)
    if not m:
        raise ValueError(f"no JSON object in model output: {raw[:200]}")
    data = json.loads(m.group(0))
    return TriageResult(**data)


def _get_client() -> Anthropic:
    from anthropic import Anthropic

    return Anthropic(api_key=get_settings().anthropic_api_key)


def classify_ticket(ticket: IncomingTicket, *, client: "Anthropic | None" = None) -> TriageResult:
    """Classify a ticket into category, priority, sentiment.

    In mock_mode we skip the network call entirely. In live mode we call Claude
    but fall back to the heuristic if the API rejects us (rate limit, bad key,
    etc.) so a single failed call never drops a ticket on the floor.
    """
    settings = get_settings()
    if settings.mock_mode:
        return _heuristic_triage(ticket)

    client = client or _get_client()
    user = TRIAGE_USER_TEMPLATE.format(subject=ticket.subject, body=ticket.body)
    try:
        resp = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=300,
            system=TRIAGE_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        text_parts = [
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ]
        return _parse_triage_json("".join(text_parts))
    except (APIError, ValueError) as exc:
        # Never let a model hiccup drop the ticket. Fall back and log the reason.
        fallback = _heuristic_triage(ticket)
        fallback.rationale = f"Fell back to heuristic: {exc}"
        return fallback

from __future__ import annotations

import pytest

from supportops.models import IncomingTicket, TicketSource
from supportops.triage import classify_ticket, detect_sentiment, draft_response


def _ticket(subject: str, body: str) -> IncomingTicket:
    return IncomingTicket(subject=subject, body=body, source=TicketSource.DIRECT)


@pytest.mark.parametrize(
    "subject,body,expected",
    [
        ("Refund for last invoice", "I was double charged on my credit card", "billing"),
        ("W-2 not in payroll system", "My paystub is missing direct deposit info", "payroll"),
        ("First login failing", "Cannot get setup on onboarding portal", "onboarding"),
        ("Vendor API 500s", "The integration partner is returning errors", "vendor"),
        ("Random question", "Just saying hi", "other"),
    ],
)
def test_classify_categories(subject, body, expected):
    result = classify_ticket(_ticket(subject, body))
    assert result.category == expected


def test_urgent_priority_from_markers():
    t = _ticket("Production down", "This is URGENT, we are blocked in production")
    result = classify_ticket(t)
    assert result.priority == "urgent"


def test_high_priority_from_frustration():
    t = _ticket("Invoice wrong again", "This is the third time, unacceptable!!!")
    result = classify_ticket(t)
    assert result.priority == "high"
    assert result.sentiment == "frustrated"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Thanks so much for the help!", "positive"),
        ("My export is broken and the error message is unclear", "negative"),
        ("STILL not working, third time I have written in!!!", "frustrated"),
        ("Just a quick question about something", "neutral"),
    ],
)
def test_sentiment_detection(text, expected):
    assert detect_sentiment(text) == expected


def test_draft_response_has_category_template_and_sources():
    ticket = _ticket("Billing question", "I think my invoice has the wrong amount")
    triage = classify_ticket(ticket)
    draft = draft_response(ticket, triage, chunks=[])
    assert "billing" in draft.text.lower() or "invoice" in draft.text.lower()
    assert isinstance(draft.cited_sources, list)

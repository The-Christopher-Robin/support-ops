"""Lightweight sentiment detection.

The heuristic here is intentionally naive: it covers the four labels the
downstream router uses and is fast enough to run inline on every ticket before
the model sees it, which lets us short-circuit obviously-urgent items even when
the model is slow or unavailable.
"""

from __future__ import annotations

import re

from ..models import Sentiment

_NEGATIVE = re.compile(
    r"\b(broken|failed|failing|error|wrong|missing|angry|upset|disappointed|bad)\b", re.I
)
_FRUSTRATED = re.compile(
    r"\b(still|again|third time|ridiculous|unacceptable|furious|!!+|refund now|cancel)\b", re.I
)
_POSITIVE = re.compile(r"\b(thank|thanks|appreciate|great|awesome|love it|perfect)\b", re.I)


def detect_sentiment(text: str) -> Sentiment:
    if _FRUSTRATED.search(text) or text.count("!") >= 3:
        return "frustrated"
    if _NEGATIVE.search(text):
        return "negative"
    if _POSITIVE.search(text):
        return "positive"
    return "neutral"

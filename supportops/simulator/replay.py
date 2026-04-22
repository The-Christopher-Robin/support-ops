"""Ticket simulator.

Generates a realistic mix of support tickets across the four categories and
pushes them at the backend. The pacing is poisson-ish so the arrival pattern
looks more like real traffic than a uniform rate, which makes the dashboard
charts interesting.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

import httpx


CATEGORIES = ("billing", "payroll", "onboarding", "vendor")


_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "billing": [
        (
            "Refund on invoice {n}",
            "Hi team, I was double charged on my credit card for invoice {n}. Can you process a refund?",
        ),
        (
            "Question about late fee",
            "Our last payment was a few days late and we got hit with a late fee. Is this something you can waive this once?",
        ),
        (
            "Plan downgrade mid-term",
            "We'd like to downgrade our plan before the end of the annual term. What are our options?",
        ),
        (
            "Failed payment keeps retrying",
            "Our card on file was replaced by the bank and payments keep failing. How do we update this without suspending the account?",
        ),
        (
            "Invoice amount looks wrong",
            "The invoice this month is higher than expected. Can someone walk me through the line items?",
        ),
    ],
    "payroll": [
        (
            "Direct deposit not working",
            "I set up direct deposit two weeks ago and I still got a paper check. What did I do wrong?",
        ),
        (
            "W-2 missing",
            "I cannot find my W-2 for last year in the portal. Can you reissue it?",
        ),
        (
            "Wrong paystub amount",
            "My paystub for this cycle looks low. I think a bonus did not get included.",
        ),
        (
            "Pay frequency change",
            "We want to switch from biweekly to semi-monthly starting next month. What's the process?",
        ),
        (
            "Garnishment question",
            "I have a wage garnishment on my paystub but I was told it should be done. Can you check?",
        ),
    ],
    "onboarding": [
        (
            "First login not working",
            "I accepted the invite but the login page keeps rejecting my password. Help please.",
        ),
        (
            "SSO setup help",
            "We want to turn on SAML SSO with Okta. What metadata do you need from us?",
        ),
        (
            "CSV import errors",
            "Our CSV import keeps failing on row 17 with an invalid email error but row 17 looks fine to me.",
        ),
        (
            "Cannot invite team",
            "When I try to invite my team I get 'seat limit reached' but our plan should have 25 seats.",
        ),
        (
            "API token access",
            "How do I enable API access for our account and get a token?",
        ),
    ],
    "vendor": [
        (
            "Partner webhook failing",
            "Our integration with the partner platform has been failing all morning. We see 500 errors.",
        ),
        (
            "Vendor onboarding email",
            "Our new supplier says they didn't receive the onboarding email. Can we resend?",
        ),
        (
            "Payment terms override",
            "We need to set Net-15 payment terms for one specific vendor. How do I override the default?",
        ),
        (
            "Dead-lettered webhook",
            "Saw a dead-lettered event on the integrations dashboard. Is it safe to replay?",
        ),
        (
            "W-9 submission issue",
            "Our supplier submitted the wrong W-9 and there's no way to redo it. What do we do?",
        ),
    ],
}


_URGENCY_PHRASES = [
    "",
    "",
    "",
    "This is urgent, we are blocked in production.",
    "Please treat this as ASAP, we can't access payroll for tomorrow.",
]


@dataclass
class SimConfig:
    tickets: int = 1000
    duration_seconds: int = 60
    backend_url: str = "http://localhost:8000"
    concurrency: int = 20


def _pick_ticket() -> dict:
    category = random.choices(CATEGORIES, weights=[0.35, 0.25, 0.25, 0.15])[0]
    subject_tpl, body_tpl = random.choice(_TEMPLATES[category])
    invoice = random.randint(1000, 9999)
    body = body_tpl.format(n=invoice)
    urgency = random.choices(_URGENCY_PHRASES, weights=[4, 4, 4, 1, 1])[0]
    if urgency:
        body = f"{body} {urgency}"
    return {
        "subject": subject_tpl.format(n=invoice),
        "body": body,
        "source": "direct",
    }


async def _send_one(client: httpx.AsyncClient, payload: dict) -> int:
    try:
        r = await client.post("/tickets", json=payload, timeout=15.0)
        return r.status_code
    except httpx.HTTPError:
        return 0


async def run(config: SimConfig) -> dict:
    interval = config.duration_seconds / max(config.tickets, 1)
    sem = asyncio.Semaphore(config.concurrency)
    sent = 0
    ok = 0

    async with httpx.AsyncClient(base_url=config.backend_url) as client:
        async def _launch(payload):
            nonlocal sent, ok
            async with sem:
                status = await _send_one(client, payload)
                sent += 1
                if 200 <= status < 300:
                    ok += 1

        tasks: list[asyncio.Task] = []
        for _ in range(config.tickets):
            tasks.append(asyncio.create_task(_launch(_pick_ticket())))
            # Poisson-ish jitter around the mean interval.
            await asyncio.sleep(random.expovariate(1.0 / interval) if interval > 0 else 0)
        await asyncio.gather(*tasks)

    return {"sent": sent, "ok": ok, "duration_s": config.duration_seconds}

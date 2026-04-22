from __future__ import annotations

from fastapi.testclient import TestClient

from supportops.api.main import app
from supportops.models import KBDocument
from supportops.rag.embedder import embed_texts
from supportops.rag.store import get_store


def test_health_endpoint():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["mock_mode"] is True


def test_create_and_list_ticket_end_to_end():
    with TestClient(app) as client:
        r = client.post(
            "/tickets",
            json={
                "source": "direct",
                "subject": "Refund question on invoice 1234",
                "body": "I think I was double charged on my credit card last month.",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["triage"]["category"] == "billing"
        assert body["draft"]["text"]

        r2 = client.get("/tickets")
        assert r2.status_code == 200
        assert len(r2.json()) >= 1


def test_zendesk_webhook_round_trip():
    with TestClient(app) as client:
        r = client.post(
            "/webhooks/zendesk",
            json={
                "ticket": {
                    "id": 99,
                    "subject": "Vendor API returning 500s",
                    "description": "Our integration partner has been failing all morning.",
                    "requester": {"email": "ops@example.com"},
                }
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["category"] == "vendor"


def test_help_center_endpoint():
    import asyncio

    store = get_store()
    docs = [
        KBDocument(
            source_path="billing/late-fees.md",
            title="Late fees",
            category="billing",
            content="Late fees are waived on a first-time basis if the invoice is paid within 10 days.",
        )
    ]
    embeddings = embed_texts([d.content for d in docs])
    asyncio.run(store.upsert(docs, embeddings))

    with TestClient(app) as client:
        r = client.post(
            "/tickets/help",
            json={"question": "Are late fees ever waived?", "category": "billing"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["retrieved"]
        assert "late" in body["answer"].lower()

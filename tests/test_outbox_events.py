from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import OutboxEvent
from tests.helpers import auth_headers, create_payload

BASE = "/api/v1/workspaces/ws_1/approval-requests"


def test_outbox_events_recorded_for_create_and_decision(client, db_engine):
    created = client.post(BASE, json=create_payload(), headers=auth_headers()).json()
    client.post(f"{BASE}/{created['id']}/approve", json={"comment": "Approved"}, headers=auth_headers())

    session_factory = sessionmaker(bind=db_engine, future=True)
    with session_factory() as session:
        events = session.scalars(
            select(OutboxEvent).where(OutboxEvent.approval_request_id == created["id"]).order_by(
                OutboxEvent.created_at
            )
        ).all()

    assert [e.event_type for e in events] == [
        "approval_request.created",
        "approval_request.approved",
    ]
    assert events[0].published_at is None
    assert events[0].payload["workspaceId"] == "ws_1"
    assert events[0].payload["requestId"] == created["id"]
    # Never leaks secrets/emails/tokens - payload is limited to known-safe fields.
    forbidden_keys = {"email", "token", "secret", "storageKey", "signedUrl", "providerUrl"}
    assert forbidden_keys.isdisjoint(events[0].payload.keys())

"""Transactional outbox for cross-service integration.

Every state-changing action writes an OutboxEvent row in the same DB
transaction as the business change, so the event can never be lost or
duplicated relative to the state it describes. A separate relay process
(see scripts/relay_outbox.py for a minimal example) polls the unpublished
rows and forwards them to a broker, marking them published. This service
does not talk to a broker directly.

Event payloads only ever contain identifiers and fields already accepted
through the public API (title/description/status/etc). They never contain
secrets, tokens, emails, storage keys, signed URLs, or provider payloads,
because this service never receives those in the first place.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import ApprovalRequest, OutboxEvent


def emit_event(
    db: Session,
    *,
    approval_request: ApprovalRequest,
    event_type: str,
    actor_user_id: str,
    extra: dict[str, Any] | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {
        "event": event_type,
        "workspaceId": approval_request.workspace_id,
        "requestId": approval_request.id,
        "sourceType": approval_request.source_type.value,
        "sourceId": approval_request.source_id,
        "status": approval_request.status.value,
        "actorUserId": actor_user_id,
        "occurredAt": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)

    event = OutboxEvent(
        workspace_id=approval_request.workspace_id,
        approval_request_id=approval_request.id,
        event_type=event_type,
        payload=payload,
    )
    db.add(event)
    return event

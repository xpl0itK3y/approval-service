from typing import Any

from sqlalchemy.orm import Session

from app.models import ApprovalRequest, AuditLogEntry


def record_audit(
    db: Session,
    *,
    approval_request: ApprovalRequest,
    action: str,
    actor_user_id: str,
    from_status: str | None,
    to_status: str | None,
    details: dict[str, Any] | None = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(
        workspace_id=approval_request.workspace_id,
        approval_request_id=approval_request.id,
        action=action,
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=to_status,
        details=details,
    )
    db.add(entry)
    return entry

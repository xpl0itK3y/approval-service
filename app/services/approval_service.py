"""Business logic for the approval-request lifecycle.

State machine: pending -> {approved, rejected, cancelled}. The three target
states are final: once reached, no further decision on that request is
accepted (see `_apply_decision`). The only way to "retry" a decision safely
is to resend the exact same request with the same Idempotency-Key, which
replays the original response instead of re-evaluating the transition.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.audit import record_audit
from app.events import emit_event
from app.exceptions import ConflictError, NotFoundError
from app.idempotency import find_replay, hash_payload, store_response
from app.models import FINAL_STATUSES, ApprovalRequest, ApprovalStatus
from app.schemas import ApprovalRequestCreate, ApprovalRequestOut


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(approval_request: ApprovalRequest) -> dict[str, Any]:
    return ApprovalRequestOut.model_validate(approval_request).model_dump(mode="json")


def create_approval_request(
    db: Session,
    *,
    workspace_id: str,
    actor_user_id: str,
    payload: ApprovalRequestCreate,
    idempotency_key: str | None,
) -> tuple[dict[str, Any], int]:
    endpoint = "create_approval_request"
    request_hash = hash_payload({"workspace_id": workspace_id, **payload.model_dump(mode="json")})

    if idempotency_key:
        replay = find_replay(
            db,
            workspace_id=workspace_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay is not None:
            return replay.body, replay.status_code

    approval_request = ApprovalRequest(
        workspace_id=workspace_id,
        source_type=payload.sourceType,
        source_id=payload.sourceId,
        title=payload.title,
        description=payload.description,
        reviewer_user_ids=payload.reviewerUserIds,
        status=ApprovalStatus.pending,
        created_by_user_id=actor_user_id,
    )
    db.add(approval_request)
    db.flush()

    record_audit(
        db,
        approval_request=approval_request,
        action="create",
        actor_user_id=actor_user_id,
        from_status=None,
        to_status=ApprovalStatus.pending.value,
    )
    emit_event(
        db,
        approval_request=approval_request,
        event_type="approval_request.created",
        actor_user_id=actor_user_id,
    )

    body = _serialize(approval_request)

    if idempotency_key:
        store_response(
            db,
            workspace_id=workspace_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status_code=201,
            body=body,
        )

    db.commit()
    return body, 201


def list_approval_requests(
    db: Session,
    *,
    workspace_id: str,
    status: ApprovalStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[ApprovalRequest], int]:
    query = db.query(ApprovalRequest).filter(ApprovalRequest.workspace_id == workspace_id)
    if status is not None:
        query = query.filter(ApprovalRequest.status == status)

    total = query.count()
    items = (
        query.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id).offset(offset).limit(limit).all()
    )
    return items, total


def get_approval_request(db: Session, *, workspace_id: str, request_id: str) -> ApprovalRequest:
    approval_request = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.workspace_id == workspace_id, ApprovalRequest.id == request_id)
        .one_or_none()
    )
    if approval_request is None:
        raise NotFoundError("Approval request not found")
    return approval_request


def _apply_decision(
    db: Session,
    *,
    workspace_id: str,
    request_id: str,
    actor_user_id: str,
    action: str,
    target_status: ApprovalStatus,
    details: dict[str, Any],
    idempotency_key: str | None,
    request_hash: str,
) -> tuple[dict[str, Any], int]:
    endpoint = f"{action}:{request_id}"

    if idempotency_key:
        replay = find_replay(
            db,
            workspace_id=workspace_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay is not None:
            return replay.body, replay.status_code

    approval_request = get_approval_request(db, workspace_id=workspace_id, request_id=request_id)

    if approval_request.status in FINAL_STATUSES:
        raise ConflictError(
            f"Approval request is already in a final state ({approval_request.status.value}) "
            "and cannot be changed. Resend with the original Idempotency-Key to replay a prior "
            "successful decision."
        )

    from_status = approval_request.status.value
    approval_request.status = target_status
    approval_request.decided_by_user_id = actor_user_id
    approval_request.decided_at = _utcnow()
    if action == "approve":
        approval_request.decision_comment = details.get("comment")
    else:
        approval_request.decision_reason = details.get("reason")

    db.flush()

    record_audit(
        db,
        approval_request=approval_request,
        action=action,
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=target_status.value,
        details=details,
    )
    emit_event(
        db,
        approval_request=approval_request,
        event_type=f"approval_request.{target_status.value}",
        actor_user_id=actor_user_id,
    )

    body = _serialize(approval_request)

    if idempotency_key:
        store_response(
            db,
            workspace_id=workspace_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status_code=200,
            body=body,
        )

    db.commit()
    return body, 200


def approve_approval_request(
    db: Session,
    *,
    workspace_id: str,
    request_id: str,
    actor_user_id: str,
    comment: str | None,
    idempotency_key: str | None,
) -> tuple[dict[str, Any], int]:
    request_hash = hash_payload({"comment": comment})
    return _apply_decision(
        db,
        workspace_id=workspace_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        action="approve",
        target_status=ApprovalStatus.approved,
        details={"comment": comment},
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )


def reject_approval_request(
    db: Session,
    *,
    workspace_id: str,
    request_id: str,
    actor_user_id: str,
    reason: str,
    idempotency_key: str | None,
) -> tuple[dict[str, Any], int]:
    request_hash = hash_payload({"reason": reason})
    return _apply_decision(
        db,
        workspace_id=workspace_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        action="reject",
        target_status=ApprovalStatus.rejected,
        details={"reason": reason},
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )


def cancel_approval_request(
    db: Session,
    *,
    workspace_id: str,
    request_id: str,
    actor_user_id: str,
    reason: str,
    idempotency_key: str | None,
) -> tuple[dict[str, Any], int]:
    request_hash = hash_payload({"reason": reason})
    return _apply_decision(
        db,
        workspace_id=workspace_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        action="cancel",
        target_status=ApprovalStatus.cancelled,
        details={"reason": reason},
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )

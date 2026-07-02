from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.auth import AuthContext, require_action
from app.db import get_db
from app.models import ApprovalStatus
from app.schemas import (
    ApprovalRequestCreate,
    ApprovalRequestListOut,
    ApprovalRequestOut,
    AuditLogEntryOut,
    CancelDecision,
    ApproveDecision,
    RejectDecision,
)
from app.services import approval_service

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/approval-requests",
    tags=["approval-requests"],
)


@router.post("", response_model=ApprovalRequestOut, status_code=status.HTTP_201_CREATED)
def create_approval_request(
    workspace_id: str,
    payload: ApprovalRequestCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_action("approval:create")),
):
    body, status_code = approval_service.create_approval_request(
        db,
        workspace_id=workspace_id,
        actor_user_id=auth.user_id,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    return ApprovalRequestOut.model_validate(body)


@router.get("", response_model=ApprovalRequestListOut)
def list_approval_requests(
    workspace_id: str,
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_action("approval:read")),
):
    items, total = approval_service.list_approval_requests(
        db, workspace_id=workspace_id, status=status_filter, limit=limit, offset=offset
    )
    return ApprovalRequestListOut(
        items=[ApprovalRequestOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{request_id}", response_model=ApprovalRequestOut)
def get_approval_request(
    workspace_id: str,
    request_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_action("approval:read")),
):
    approval_request = approval_service.get_approval_request(
        db, workspace_id=workspace_id, request_id=request_id
    )
    return ApprovalRequestOut.model_validate(approval_request)


@router.get("/{request_id}/audit-log", response_model=list[AuditLogEntryOut])
def get_audit_log(
    workspace_id: str,
    request_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_action("approval:read")),
):
    approval_request = approval_service.get_approval_request(
        db, workspace_id=workspace_id, request_id=request_id
    )
    return [AuditLogEntryOut.model_validate(entry) for entry in approval_request.audit_entries]


@router.post("/{request_id}/approve", response_model=ApprovalRequestOut)
def approve_approval_request(
    workspace_id: str,
    request_id: str,
    payload: ApproveDecision,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_action("approval:decide")),
):
    body, _ = approval_service.approve_approval_request(
        db,
        workspace_id=workspace_id,
        request_id=request_id,
        actor_user_id=auth.user_id,
        comment=payload.comment,
        idempotency_key=idempotency_key,
    )
    return ApprovalRequestOut.model_validate(body)


@router.post("/{request_id}/reject", response_model=ApprovalRequestOut)
def reject_approval_request(
    workspace_id: str,
    request_id: str,
    payload: RejectDecision,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_action("approval:decide")),
):
    body, _ = approval_service.reject_approval_request(
        db,
        workspace_id=workspace_id,
        request_id=request_id,
        actor_user_id=auth.user_id,
        reason=payload.reason,
        idempotency_key=idempotency_key,
    )
    return ApprovalRequestOut.model_validate(body)


@router.post("/{request_id}/cancel", response_model=ApprovalRequestOut)
def cancel_approval_request(
    workspace_id: str,
    request_id: str,
    payload: CancelDecision,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_action("approval:cancel")),
):
    body, _ = approval_service.cancel_approval_request(
        db,
        workspace_id=workspace_id,
        request_id=request_id,
        actor_user_id=auth.user_id,
        reason=payload.reason,
        idempotency_key=idempotency_key,
    )
    return ApprovalRequestOut.model_validate(body)

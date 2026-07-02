import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(str, enum.Enum):
    publication = "publication"
    scenario = "scenario"
    edit = "edit"
    external = "external"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


FINAL_STATUSES = {ApprovalStatus.approved, ApprovalStatus.rejected, ApprovalStatus.cancelled}


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_workspace_id", "workspace_id"),
        Index("ix_approval_requests_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(128), nullable=False)

    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewer_user_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status"), nullable=False, default=ApprovalStatus.pending
    )

    created_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    decided_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    audit_entries: Mapped[list["AuditLogEntry"]] = relationship(
        back_populates="approval_request", cascade="all, delete-orphan"
    )


class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"
    __table_args__ = (Index("ix_audit_log_workspace_request", "workspace_id", "approval_request_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approval_requests.id"), nullable=False
    )

    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(128), nullable=False)

    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    approval_request: Mapped["ApprovalRequest"] = relationship(back_populates="audit_entries")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_events_published_at", "published_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_request_id: Mapped[str] = mapped_column(String(36), nullable=False)

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdempotencyKeyRecord(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("workspace_id", "endpoint", "idempotency_key", name="uq_idempotency_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)

    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status_code: Mapped[int] = mapped_column(nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

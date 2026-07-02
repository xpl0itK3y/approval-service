from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ApprovalStatus, SourceType


class ApprovalRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sourceType: SourceType
    sourceId: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=10_000)
    reviewerUserIds: list[str] = Field(min_length=1)

    @field_validator("reviewerUserIds")
    @classmethod
    def _no_blank_reviewers(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value]
        if any(not v for v in cleaned):
            raise ValueError("reviewerUserIds must not contain blank ids")
        return cleaned


class ApproveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: str | None = Field(default=None, max_length=10_000)


class RejectDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=10_000)


class CancelDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=10_000)


class ApprovalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspaceId: str = Field(validation_alias="workspace_id")
    sourceType: SourceType = Field(validation_alias="source_type")
    sourceId: str = Field(validation_alias="source_id")
    title: str
    description: str | None
    reviewerUserIds: list[str] = Field(validation_alias="reviewer_user_ids")
    status: ApprovalStatus
    createdByUserId: str = Field(validation_alias="created_by_user_id")
    createdAt: datetime = Field(validation_alias="created_at")
    updatedAt: datetime = Field(validation_alias="updated_at")
    decidedByUserId: str | None = Field(validation_alias="decided_by_user_id")
    decidedAt: datetime | None = Field(validation_alias="decided_at")
    decisionComment: str | None = Field(validation_alias="decision_comment")
    decisionReason: str | None = Field(validation_alias="decision_reason")


class ApprovalRequestListOut(BaseModel):
    items: list[ApprovalRequestOut]
    total: int
    limit: int
    offset: int


class AuditLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    actorUserId: str = Field(validation_alias="actor_user_id")
    fromStatus: str | None = Field(validation_alias="from_status")
    toStatus: str | None = Field(validation_alias="to_status")
    details: dict | None
    createdAt: datetime = Field(validation_alias="created_at")


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody

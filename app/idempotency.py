"""Idempotency-Key handling shared by create and decision endpoints.

Callers may send an `Idempotency-Key` header. Replays of the exact same
request (same workspace + endpoint + key + body) return the original
response instead of re-executing the mutation. Reusing a key with a
different body is rejected with 409, since that almost certainly means the
client mixed up two different logical requests.

Records are scoped to (workspace_id, endpoint, idempotency_key) so the same
key value can be reused safely across unrelated endpoints/requests.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IdempotencyKeyRecord


def hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdempotencyReplay:
    status_code: int
    body: dict[str, Any]


class IdempotencyKeyConflict(Exception):
    """Same key reused with a different request payload."""


def find_replay(
    db: Session, *, workspace_id: str, endpoint: str, idempotency_key: str, request_hash: str
) -> IdempotencyReplay | None:
    existing = (
        db.query(IdempotencyKeyRecord)
        .filter_by(workspace_id=workspace_id, endpoint=endpoint, idempotency_key=idempotency_key)
        .one_or_none()
    )
    if existing is None:
        return None
    if existing.request_hash != request_hash:
        raise IdempotencyKeyConflict(
            "Idempotency-Key was already used for a different request payload"
        )
    return IdempotencyReplay(status_code=existing.response_status_code, body=existing.response_body)


def store_response(
    db: Session,
    *,
    workspace_id: str,
    endpoint: str,
    idempotency_key: str,
    request_hash: str,
    status_code: int,
    body: dict[str, Any],
) -> None:
    record = IdempotencyKeyRecord(
        workspace_id=workspace_id,
        endpoint=endpoint,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        response_status_code=status_code,
        response_body=body,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        # A concurrent request won the race and stored a record first.
        db.rollback()
        raise IdempotencyKeyConflict(
            "Idempotency-Key was already used concurrently"
        ) from exc

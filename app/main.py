import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import ApprovalServiceError
from app.idempotency import IdempotencyKeyConflict
from app.routers import approval_requests, health

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("approval_service")

app = FastAPI(title="approval-service", version="1.0.0")

app.include_router(health.router)
app.include_router(approval_requests.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    started = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - started) * 1000, 2)
    # Deliberately log only method/path/status/duration and coarse identifiers -
    # never headers or body, so secrets/tokens/PII can never leak into logs.
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(ApprovalServiceError)
async def handle_service_error(request: Request, exc: ApprovalServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(IdempotencyKeyConflict)
async def handle_idempotency_conflict(request: Request, exc: IdempotencyKeyConflict):
    return JSONResponse(
        status_code=409,
        content={"error": {"code": "idempotency_key_conflict", "message": str(exc)}},
    )

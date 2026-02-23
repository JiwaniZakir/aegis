"""ClawdBot — FastAPI application factory."""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.content import router as content_router
from app.api.v1.email import router as email_router
from app.api.v1.finance import router as finance_router
from app.api.v1.health import router as health_data_router
from app.api.v1.social import router as social_router
from app.config import get_settings
from app.database import async_session_factory
from app.logging import configure_logging
from app.models.audit import AuditLog

configure_logging()
logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    is_prod = settings.environment == "production"
    app = FastAPI(
        title="ClawdBot",
        description="Personal intelligence platform API",
        version="0.1.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def audit_middleware(request: Request, call_next: object) -> Response:
        """Log every API request to the audit table."""
        start = time.monotonic()
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response: Response = await call_next(request)  # type: ignore[call-arg]
        elapsed_ms = round((time.monotonic() - start) * 1000)

        client_ip = request.client.host if request.client else None

        # Write audit log (skip health checks to reduce noise)
        if request.url.path not in {"/health", "/docs", "/redoc", "/openapi.json"}:
            try:
                async with async_session_factory() as session:
                    entry = AuditLog(
                        action=request.method,
                        resource_type="api",
                        resource_id=request.url.path,
                        ip_address=client_ip,
                        metadata_={
                            "status_code": response.status_code,
                            "elapsed_ms": elapsed_ms,
                            "request_id": request_id,
                        },
                    )
                    session.add(entry)
                    await session.commit()
            except Exception:
                logger.error("audit_write_failed", path=request.url.path)

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=elapsed_ms,
        )

        structlog.contextvars.unbind_contextvars("request_id")
        return response

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "clawdbot-api"}

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(calendar_router, prefix="/api/v1")
    app.include_router(content_router, prefix="/api/v1")
    app.include_router(email_router, prefix="/api/v1")
    app.include_router(finance_router, prefix="/api/v1")
    app.include_router(health_data_router, prefix="/api/v1")
    app.include_router(social_router, prefix="/api/v1")

    return app


app = create_app()

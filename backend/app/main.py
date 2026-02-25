"""Aegis — FastAPI application factory."""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.content import router as content_router
from app.api.v1.email import router as email_router
from app.api.v1.finance import router as finance_router
from app.api.v1.health import router as health_data_router
from app.api.v1.insights import router as insights_router
from app.api.v1.productivity import router as productivity_router
from app.api.v1.security import router as security_router
from app.api.v1.social import router as social_router
from app.api.v1.whatsapp import router as whatsapp_router
from app.config import get_settings
from app.database import async_session_factory
from app.logging import configure_logging
from app.models.audit import AuditLog

configure_logging()
logger = structlog.get_logger()


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP, respecting X-Forwarded-For behind reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2 — take the first (client)
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _get_user_id_from_request(request: Request) -> str | None:
    """Attempt to extract user_id from JWT in Authorization header (best-effort)."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        import jwt as pyjwt

        settings = get_settings()
        payload = pyjwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        return None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    is_prod = settings.environment == "production"
    app = FastAPI(
        title="Aegis",
        description="Personal intelligence platform API",
        version="0.1.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    # CORS — origins from config, not hardcoded
    # Note: CSRF middleware is intentionally omitted. This API uses Bearer token
    # authentication (not cookies), so it is inherently immune to CSRF attacks.
    # The SPA console sends JWTs via the Authorization header, which browsers
    # do not attach automatically on cross-origin requests.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
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

        # Use X-Forwarded-For behind Traefik
        client_ip = _get_client_ip(request)

        # Associate audit log with authenticated user when possible
        user_id_str = _get_user_id_from_request(request)
        user_uuid = None
        if user_id_str:
            import contextlib

            with contextlib.suppress(ValueError):
                user_uuid = uuid.UUID(user_id_str)

        # Write audit log (skip health checks to reduce noise)
        if request.url.path not in {"/health", "/docs", "/redoc", "/openapi.json"}:
            try:
                async with async_session_factory() as session:
                    entry = AuditLog(
                        user_id=user_uuid,
                        action=request.method,
                        resource_type="api",
                        resource_id=request.url.path,
                        ip_address=client_ip,
                        metadata_={
                            "status_code": response.status_code,
                            "elapsed_ms": elapsed_ms,
                            "request_id": request_id,
                            "user_agent": request.headers.get("user-agent", ""),
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
            client_ip=client_ip,
        )

        structlog.contextvars.unbind_contextvars("request_id")
        return response

    # Global handler for uncaught integration errors — returns 503 instead of 500
    from app.integrations.blackboard_client import BlackboardAuthError
    from app.integrations.linkedin_client import LinkedInClientError
    from app.integrations.news_aggregator import NewsAggregatorError
    from app.integrations.pearson_scraper import PearsonScraperError
    from app.integrations.schwab_client import SchwabAuthError, SchwabTradeError
    from app.integrations.web_crawler import WebCrawlerError
    from app.integrations.whatsapp_bridge import WhatsAppBridgeError
    from app.integrations.x_client import XClientError

    _integration_errors = (
        XClientError,
        LinkedInClientError,
        NewsAggregatorError,
        WebCrawlerError,
        SchwabAuthError,
        SchwabTradeError,
        PearsonScraperError,
        BlackboardAuthError,
        WhatsAppBridgeError,
    )

    for exc_cls in _integration_errors:

        @app.exception_handler(exc_cls)
        async def _handle_integration_error(
            request: Request,
            exc: Exception,
        ) -> JSONResponse:
            logger.warning(
                "integration_error",
                error=type(exc).__name__,
                detail=str(exc),
                path=request.url.path,
            )
            return JSONResponse(
                status_code=503,
                content={"detail": str(exc)},
            )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "aegis-api"}

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(calendar_router, prefix="/api/v1")
    app.include_router(contacts_router, prefix="/api/v1")
    app.include_router(content_router, prefix="/api/v1")
    app.include_router(email_router, prefix="/api/v1")
    app.include_router(finance_router, prefix="/api/v1")
    app.include_router(health_data_router, prefix="/api/v1")
    app.include_router(insights_router, prefix="/api/v1")
    app.include_router(productivity_router, prefix="/api/v1")
    app.include_router(security_router, prefix="/api/v1")
    app.include_router(social_router, prefix="/api/v1")
    app.include_router(whatsapp_router, prefix="/api/v1")

    return app


app = create_app()

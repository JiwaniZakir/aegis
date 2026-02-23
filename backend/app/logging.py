"""Structured logging setup with secret redaction."""

from __future__ import annotations

import re

import structlog

_REDACT_RE = (
    r"(password|secret|token|key|authorization|cookie)"
    r"(['\"]?\s*[:=]\s*['\"]?)([^\s'\"]{4})[^\s'\"]*"
)
REDACT_PATTERNS = [re.compile(_REDACT_RE, re.IGNORECASE)]

REDACT_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "key",
        "authorization",
        "api_key",
        "access_token",
        "refresh_token",
        "jwt",
        "hashed_password",
        "totp_secret",
        "encrypted_value",
    }
)


def redact_sensitive(
    _logger: object,
    _method: str,
    event_dict: dict,
) -> dict:
    """Structlog processor that redacts sensitive values from log output."""
    for k, v in list(event_dict.items()):
        if k in REDACT_KEYS and isinstance(v, str) and len(v) > 4:  # noqa: PLR2004
            event_dict[k] = v[:4] + "****"
        elif isinstance(v, str):
            for pattern in REDACT_PATTERNS:
                v = pattern.sub(r"\1\2\3****", v)
            event_dict[k] = v
    return event_dict


def configure_logging() -> None:
    """Configure structlog with JSON output and secret redaction."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_sensitive,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

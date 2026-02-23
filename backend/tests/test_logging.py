"""Tests for structured logging with secret redaction."""

from __future__ import annotations

from app.logging import REDACT_KEYS, REDACT_PATTERNS, configure_logging, redact_sensitive


def test_redact_password_in_keys():
    """Sensitive keys have their values redacted."""
    event = {"password": "supersecretpassword", "user": "admin"}
    result = redact_sensitive(None, None, event)
    assert result["password"] == "supe****"
    assert result["user"] == "admin"


def test_redact_api_key():
    """API key values are redacted."""
    event = {"api_key": "sk-1234567890abcdef"}
    result = redact_sensitive(None, None, event)
    assert "1234567890abcdef" not in result["api_key"]
    assert result["api_key"].startswith("sk-1****")


def test_redact_token():
    """Token values are redacted."""
    event = {"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc"}
    result = redact_sensitive(None, None, event)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result["access_token"]


def test_short_values_not_redacted():
    """Values <= 4 chars in sensitive keys are not redacted."""
    event = {"token": "abc"}
    result = redact_sensitive(None, None, event)
    assert result["token"] == "abc"


def test_non_sensitive_keys_unchanged():
    """Non-sensitive keys pass through unchanged."""
    event = {"username": "admin", "status": "ok", "count": 42}
    result = redact_sensitive(None, None, event)
    assert result == {"username": "admin", "status": "ok", "count": 42}


# ---------------------------------------------------------------------------
# Additional redaction tests
# ---------------------------------------------------------------------------


def test_redact_refresh_token():
    """Refresh token values are redacted."""
    event = {"refresh_token": "rt_abcdefghijklmnop12345"}
    result = redact_sensitive(None, None, event)
    assert "abcdefghijklmnop12345" not in result["refresh_token"]
    assert result["refresh_token"].startswith("rt_a****")


def test_redact_jwt():
    """JWT values are redacted."""
    event = {"jwt": "eyJhbGciOiJIUzI1NiJ9.payload.signature"}
    result = redact_sensitive(None, None, event)
    assert "payload" not in result["jwt"]
    assert result["jwt"].startswith("eyJh****")


def test_redact_secret():
    """Secret values are redacted."""
    event = {"secret": "my_super_secret_value_here"}
    result = redact_sensitive(None, None, event)
    assert "super_secret_value_here" not in result["secret"]
    assert result["secret"].startswith("my_s****")


def test_redact_hashed_password():
    """Hashed password values are redacted."""
    event = {"hashed_password": "$2b$12$LJ3m4ys9tRHG9UxzF3t5yOaN7NbQm0"}
    result = redact_sensitive(None, None, event)
    assert "LJ3m4ys9tRHG9UxzF3t5yOaN7NbQm0" not in result["hashed_password"]
    assert result["hashed_password"].startswith("$2b$****")


def test_redact_encrypted_value():
    """encrypted_value key is redacted."""
    event = {"encrypted_value": "aes256gcm:nonce:ciphertext:tag"}
    result = redact_sensitive(None, None, event)
    assert "nonce:ciphertext:tag" not in result["encrypted_value"]


def test_redact_pattern_in_string_values():
    """Inline password patterns in non-sensitive key values are redacted."""
    event = {"message": 'Connected with password="hunter2_secret_stuff"'}
    result = redact_sensitive(None, None, event)
    assert "hunter2_secret_stuff" not in result["message"]
    assert "password" in result["message"]


def test_numeric_values_pass_through():
    """Non-string values (int, float, None, bool) pass through unchanged."""
    event = {"count": 42, "rate": 3.14, "enabled": True, "extra": None}
    result = redact_sensitive(None, None, event)
    assert result["count"] == 42
    assert result["rate"] == 3.14
    assert result["enabled"] is True
    assert result["extra"] is None


def test_redact_keys_constant_is_frozenset():
    """REDACT_KEYS is a frozenset for immutability."""
    assert isinstance(REDACT_KEYS, frozenset)
    assert len(REDACT_KEYS) > 0


def test_redact_patterns_compiled():
    """REDACT_PATTERNS contains compiled regex patterns."""
    import re

    assert isinstance(REDACT_PATTERNS, list)
    assert len(REDACT_PATTERNS) > 0
    for pattern in REDACT_PATTERNS:
        assert isinstance(pattern, re.Pattern)


# ---------------------------------------------------------------------------
# Structlog configuration tests
# ---------------------------------------------------------------------------


def test_configure_logging_runs_without_error():
    """configure_logging completes without raising."""
    configure_logging()


def test_configure_logging_sets_json_renderer():
    """After configuration, structlog uses the JSON renderer."""
    import structlog

    configure_logging()
    config = structlog.get_config()
    processors = config.get("processors", [])
    processor_types = [type(p).__name__ for p in processors]
    assert "JSONRenderer" in processor_types


def test_configure_logging_includes_redaction():
    """After configuration, structlog includes the redact_sensitive processor."""
    import structlog

    configure_logging()
    config = structlog.get_config()
    processors = config.get("processors", [])
    assert redact_sensitive in processors

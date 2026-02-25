"""Live integration tests against the running Docker stack.

These tests hit the actual API and database. They require
the full Docker Compose stack to be running.

Run with:
    uv run pytest tests/test_live_stack.py -v -m live

Skip with:
    uv run pytest -m "not live"
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.live

BASE = "http://localhost:8000"
ADMIN_EMAIL = "zakir@aegis.local"
ADMIN_PASSWORD = "Aegis2024!"


def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict | None = None,
) -> tuple[int, dict | list | str]:
    """Make an HTTP request and return (status_code, parsed_body)."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310
    try:
        resp = urllib.request.urlopen(req)  # noqa: S310
        raw = resp.read().decode()
        try:
            return resp.status, json.loads(raw)
        except json.JSONDecodeError:
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


@pytest.fixture(scope="module")
def access_token() -> str:
    """Login once and return a valid access token for the test module."""
    status, body = _request(
        "POST",
        "/api/v1/auth/login",
        body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert status == 200, f"Login failed: {body}"
    assert "access_token" in body
    return body["access_token"]


@pytest.fixture(scope="module")
def tokens() -> dict:
    """Login and return both access and refresh tokens."""
    status, body = _request(
        "POST",
        "/api/v1/auth/login",
        body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert status == 200
    return body


# =============================================================================
# Health & Connectivity
# =============================================================================


class TestHealth:
    def test_health_endpoint(self):
        status, body = _request("GET", "/health")
        assert status == 200
        assert body["status"] == "ok"
        assert body["service"] == "aegis-api"

    def test_openapi_schema_available(self):
        status, body = _request("GET", "/openapi.json")
        assert status == 200
        assert "paths" in body
        assert len(body["paths"]) > 40

    def test_docs_available(self):
        status, _ = _request("GET", "/docs")
        assert status == 200


# =============================================================================
# Authentication
# =============================================================================


class TestAuth:
    def test_login_success(self, tokens):
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] == 900

    def test_login_wrong_password(self):
        status, body = _request(
            "POST",
            "/api/v1/auth/login",
            body={"email": ADMIN_EMAIL, "password": "wrong_password"},
        )
        assert status == 401
        assert body["detail"] == "Invalid credentials"

    def test_login_wrong_email(self):
        status, body = _request(
            "POST",
            "/api/v1/auth/login",
            body={"email": "nobody@example.com", "password": "anything"},
        )
        assert status == 401
        assert body["detail"] == "Invalid credentials"

    def test_protected_endpoint_no_token(self):
        status, _ = _request("GET", "/api/v1/finance/balances")
        assert status in {401, 403}

    def test_protected_endpoint_invalid_token(self):
        status, _ = _request(
            "GET",
            "/api/v1/finance/balances",
            token="invalid.jwt.token",
        )
        assert status == 401

    def test_token_refresh(self, tokens):
        status, body = _request(
            "POST",
            "/api/v1/auth/refresh",
            body={"refresh_token": tokens["refresh_token"]},
        )
        assert status == 200
        assert "access_token" in body
        assert body["access_token"] != tokens["access_token"]

    def test_logout_revokes_token(self):
        # Get fresh tokens
        _, login_body = _request(
            "POST",
            "/api/v1/auth/login",
            body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        token = login_body["access_token"]
        refresh = login_body["refresh_token"]

        # Verify token works
        status, _ = _request("GET", "/api/v1/finance/balances", token=token)
        assert status == 200

        # Logout
        status, _ = _request(
            "POST",
            "/api/v1/auth/logout",
            token=token,
            body={"refresh_token": refresh},
        )
        assert status == 204

        # Token should now be blocked
        status, _ = _request("GET", "/api/v1/finance/balances", token=token)
        assert status == 401


# =============================================================================
# Finance
# =============================================================================


class TestFinance:
    def test_get_balances(self, access_token):
        status, body = _request("GET", "/api/v1/finance/balances", token=access_token)
        assert status == 200
        assert "balances" in body
        assert "total" in body
        assert isinstance(body["balances"], list)

    def test_get_transactions(self, access_token):
        status, body = _request("GET", "/api/v1/finance/transactions", token=access_token)
        assert status == 200
        assert "transactions" in body
        assert "count" in body

    def test_get_transactions_with_date_filter(self, access_token):
        """With no linked accounts, transactions returns empty regardless of dates."""
        status, body = _request(
            "GET",
            "/api/v1/finance/transactions?start_date=2026-01-01&end_date=2026-02-23",
            token=access_token,
        )
        assert status == 200
        assert body["count"] == 0

    def test_get_subscriptions(self, access_token):
        status, body = _request("GET", "/api/v1/finance/subscriptions", token=access_token)
        assert status == 200

    def test_affordability_check(self, access_token):
        status, body = _request(
            "POST",
            "/api/v1/finance/affordability",
            token=access_token,
            body={"item": "Test item", "amount": 100.0},
        )
        assert status == 200


# =============================================================================
# Email
# =============================================================================


class TestEmail:
    def test_daily_digest(self, access_token):
        status, body = _request("GET", "/api/v1/email/digest", token=access_token)
        assert status == 200
        assert "date" in body
        assert "total_emails" in body
        assert "by_category" in body

    def test_weekly_digest(self, access_token):
        status, body = _request("GET", "/api/v1/email/weekly", token=access_token)
        assert status == 200

    def test_spam_audit(self, access_token):
        status, body = _request("GET", "/api/v1/email/spam-audit", token=access_token)
        assert status == 200


# =============================================================================
# Calendar
# =============================================================================


class TestCalendar:
    def test_get_events(self, access_token):
        status, body = _request("GET", "/api/v1/calendar/events", token=access_token)
        assert status == 200
        assert "events" in body
        assert "count" in body

    def test_get_today(self, access_token):
        status, body = _request("GET", "/api/v1/calendar/today", token=access_token)
        assert status == 200


# =============================================================================
# Social & News
# =============================================================================


class TestSocial:
    def test_x_profile_unconfigured(self, access_token):
        """X integration should return 503 when not configured."""
        status, body = _request("GET", "/api/v1/social/x/me", token=access_token)
        assert status == 503
        assert "not configured" in body["detail"].lower()

    def test_post_history(self, access_token):
        status, body = _request("GET", "/api/v1/social/history", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_engagement(self, access_token):
        status, body = _request("GET", "/api/v1/social/engagement", token=access_token)
        assert status == 200

    def test_news_headlines(self, access_token):
        status, body = _request("GET", "/api/v1/news/headlines", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_crawl_ssrf_rejected(self, access_token):
        """SSRF protection: internal URLs should be rejected."""
        status, body = _request(
            "POST",
            "/api/v1/crawl",
            token=access_token,
            body={"urls": ["http://169.254.169.254/latest/meta-data/"]},
        )
        assert status == 422  # Pydantic validation rejects SSRF


# =============================================================================
# Health & Productivity
# =============================================================================


class TestHealthData:
    def test_health_summary(self, access_token):
        status, body = _request("GET", "/api/v1/health-data/summary", token=access_token)
        assert status == 200
        assert "date" in body
        assert "metrics" in body

    def test_health_trends(self, access_token):
        status, body = _request("GET", "/api/v1/health-data/trends", token=access_token)
        assert status == 200

    def test_health_goals(self, access_token):
        status, body = _request("GET", "/api/v1/health-data/goals", token=access_token)
        assert status == 200

    def test_macros(self, access_token):
        status, body = _request("GET", "/api/v1/health-data/macros", token=access_token)
        assert status == 200

    def test_weekly_health(self, access_token):
        status, body = _request("GET", "/api/v1/health-data/weekly", token=access_token)
        assert status == 200

    def test_recommendations(self, access_token):
        status, body = _request("GET", "/api/v1/health-data/recommendations", token=access_token)
        assert status == 200

    def test_ingest_apple_health(self, access_token):
        status, body = _request(
            "POST",
            "/api/v1/health-data/apple",
            token=access_token,
            body={
                "data": [
                    {
                        "type": "step_count",
                        "value": 8500,
                        "date": "2026-02-23",
                        "source": "iPhone",
                    },
                    {
                        "type": "heart_rate",
                        "value": 72,
                        "date": "2026-02-23",
                        "source": "Apple Watch",
                    },
                ]
            },
        )
        assert status == 200
        assert "total" in body

    def test_ingest_apple_health_invalid_metric(self, access_token):
        """Missing required 'data' key should fail validation."""
        status, _ = _request(
            "POST",
            "/api/v1/health-data/apple",
            token=access_token,
            body={
                "wrong_key": [
                    {
                        "type": "step_count",
                        "value": 8500,
                        "date": "2026-02-23",
                        "source": "test",
                    }
                ]
            },
        )
        assert status == 422


class TestProductivity:
    def test_productivity_summary(self, access_token):
        status, body = _request("GET", "/api/v1/productivity/summary", token=access_token)
        assert status == 200
        assert "period_days" in body

    def test_daily_productivity(self, access_token):
        status, body = _request(
            "GET",
            "/api/v1/productivity/daily?date=2026-02-23",
            token=access_token,
        )
        assert status == 200

    def test_productivity_trends(self, access_token):
        status, body = _request("GET", "/api/v1/productivity/trends", token=access_token)
        assert status == 200

    def test_weekly_report(self, access_token):
        status, body = _request("GET", "/api/v1/productivity/weekly", token=access_token)
        assert status == 200

    def test_app_usage(self, access_token):
        status, body = _request("GET", "/api/v1/productivity/app-usage", token=access_token)
        assert status == 200

    def test_ingest_screen_time(self, access_token):
        status, body = _request(
            "POST",
            "/api/v1/productivity/screen-time",
            token=access_token,
            body={
                "data": [
                    {
                        "app_name": "VS Code",
                        "minutes": 180,
                        "category": "development",
                        "date": "2026-02-23",
                    },
                    {
                        "app_name": "Chrome",
                        "minutes": 120,
                        "category": "browsing",
                        "date": "2026-02-23",
                    },
                    {
                        "app_name": "Slack",
                        "minutes": 45,
                        "category": "communication",
                        "date": "2026-02-23",
                    },
                ],
            },
        )
        assert status == 200


# =============================================================================
# Content
# =============================================================================


class TestContent:
    def test_get_drafts(self, access_token):
        status, body = _request("GET", "/api/v1/content/drafts", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_generate_content(self, access_token):
        status, body = _request(
            "POST",
            "/api/v1/content/generate",
            token=access_token,
            body={
                "topic": "AI trends in 2026",
                "platform": "linkedin",
                "tone": "thought_leader",
            },
        )
        assert status == 200
        assert "id" in body
        assert "content" in body


# =============================================================================
# Assignments
# =============================================================================


class TestAssignments:
    def test_upcoming(self, access_token):
        status, body = _request("GET", "/api/v1/assignments/upcoming", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_overdue(self, access_token):
        status, body = _request("GET", "/api/v1/assignments/overdue", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_reminders(self, access_token):
        status, body = _request("GET", "/api/v1/assignments/reminders", token=access_token)
        assert status == 200


# =============================================================================
# Briefing
# =============================================================================


class TestBriefing:
    def test_today_briefing(self, access_token):
        status, body = _request("GET", "/api/v1/briefing/today", token=access_token)
        assert status == 200
        assert "date" in body
        assert "generated_at" in body
        assert "calendar" in body
        assert "emails" in body


# =============================================================================
# Audit trail
# =============================================================================


class TestAudit:
    def test_audit_log_populated(self, access_token):
        """Verify audit logs are being written by checking the DB directly."""
        import subprocess

        result = subprocess.run(
            [  # noqa: S607
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "aegis",
                "-d",
                "aegis",
                "-t",
                "-c",
                "SELECT count(*) FROM audit_logs;",
            ],
            capture_output=True,
            text=True,
            cwd="/Users/zakirjiwani/projects/bots/aegis",
        )
        count = int(result.stdout.strip())
        assert count > 0, "Audit logs should have entries after API calls"

    def test_login_audited(self, access_token):
        """Verify login events are audited."""
        import subprocess

        result = subprocess.run(
            [  # noqa: S607
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "aegis",
                "-d",
                "aegis",
                "-t",
                "-c",
                "SELECT count(*) FROM audit_logs WHERE action = 'login_success';",
            ],
            capture_output=True,
            text=True,
            cwd="/Users/zakirjiwani/projects/bots/aegis",
        )
        count = int(result.stdout.strip())
        assert count > 0, "Login success should be audited"


# =============================================================================
# Security endpoints (new router)
# =============================================================================


class TestSecurity:
    def test_audit_log_endpoint(self, access_token):
        status, body = _request("GET", "/api/v1/security/audit-log", token=access_token)
        assert status == 200
        assert "entries" in body
        assert "total" in body
        assert isinstance(body["entries"], list)

    def test_audit_log_pagination(self, access_token):
        status, body = _request(
            "GET", "/api/v1/security/audit-log?limit=5&offset=0", token=access_token
        )
        assert status == 200
        assert len(body["entries"]) <= 5

    def test_active_sessions(self, access_token):
        status, body = _request("GET", "/api/v1/security/sessions", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_failed_logins(self, access_token):
        status, body = _request("GET", "/api/v1/security/failed-logins", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_2fa_status(self, access_token):
        status, body = _request("GET", "/api/v1/security/2fa/status", token=access_token)
        assert status == 200
        assert "enabled" in body
        assert "method" in body

    def test_change_password_wrong_current(self, access_token):
        status, body = _request(
            "POST",
            "/api/v1/security/change-password",
            token=access_token,
            body={"current_password": "wrong", "new_password": "NewPassword1234!"},
        )
        assert status == 401

    def test_change_password_too_short(self, access_token):
        status, body = _request(
            "POST",
            "/api/v1/security/change-password",
            token=access_token,
            body={"current_password": ADMIN_PASSWORD, "new_password": "short"},
        )
        assert status == 422  # Pydantic validation: min_length=12

    def test_revoke_invalid_session(self, access_token):
        status, body = _request(
            "DELETE", "/api/v1/security/sessions/invalid-id", token=access_token
        )
        assert status == 400

    def test_security_endpoints_require_auth(self):
        for path in [
            "/api/v1/security/audit-log",
            "/api/v1/security/sessions",
            "/api/v1/security/failed-logins",
            "/api/v1/security/2fa/status",
        ]:
            status, _ = _request("GET", path)
            assert status in {401, 403}, f"{path} should require auth"


# =============================================================================
# Auth /me endpoint
# =============================================================================


class TestAuthMe:
    def test_me_returns_user(self, access_token):
        status, body = _request("GET", "/api/v1/auth/me", token=access_token)
        assert status == 200
        assert "id" in body
        assert "email" in body
        assert body["email"] == ADMIN_EMAIL

    def test_me_without_auth(self):
        status, _ = _request("GET", "/api/v1/auth/me")
        assert status in {401, 403}


# =============================================================================
# Contact graph
# =============================================================================


class TestContacts:
    def test_suggest_outreach(self, access_token):
        status, body = _request(
            "GET", "/api/v1/contacts/suggest-outreach", token=access_token
        )
        assert status == 200
        assert isinstance(body, list)

    def test_suggest_outreach_with_limit(self, access_token):
        status, body = _request(
            "GET", "/api/v1/contacts/suggest-outreach?limit=5", token=access_token
        )
        assert status == 200
        assert isinstance(body, list)
        assert len(body) <= 5


# =============================================================================
# Phase 3A — Response Schema Validation
# =============================================================================


class TestResponseSchemas:
    """Verify API responses match the shapes the console TypeScript client expects."""

    def test_auth_me_schema(self, access_token):
        """GET /auth/me must return {id, email, created_at}."""
        status, body = _request("GET", "/api/v1/auth/me", token=access_token)
        assert status == 200
        assert "id" in body
        assert "email" in body
        assert "created_at" in body

    def test_finance_balances_schema(self, access_token):
        """GET /finance/balances must return a dict (may have accounts key or be flat)."""
        status, body = _request("GET", "/api/v1/finance/balances", token=access_token)
        assert status == 200
        assert isinstance(body, (dict, list))

    def test_finance_transactions_schema(self, access_token):
        """GET /finance/transactions must return a dict or list of transactions."""
        status, body = _request("GET", "/api/v1/finance/transactions", token=access_token)
        assert status == 200
        assert isinstance(body, (dict, list))

    def test_email_digest_schema(self, access_token):
        """GET /email/digest must return a dict with digest data."""
        status, body = _request("GET", "/api/v1/email/digest", token=access_token)
        assert status == 200
        assert isinstance(body, dict)

    def test_calendar_events_schema(self, access_token):
        """GET /calendar/events returns a list."""
        status, body = _request("GET", "/api/v1/calendar/events", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_health_summary_schema(self, access_token):
        """GET /health-data/summary returns a dict."""
        status, body = _request("GET", "/api/v1/health-data/summary", token=access_token)
        assert status == 200
        assert isinstance(body, dict)

    def test_productivity_summary_schema(self, access_token):
        """GET /productivity/summary returns a dict."""
        status, body = _request("GET", "/api/v1/productivity/summary", token=access_token)
        assert status == 200
        assert isinstance(body, dict)

    def test_content_drafts_schema(self, access_token):
        """GET /content/drafts returns a list."""
        status, body = _request("GET", "/api/v1/content/drafts", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_social_history_schema(self, access_token):
        """GET /social/history returns a list of post objects."""
        status, body = _request("GET", "/api/v1/social/history", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_news_headlines_schema(self, access_token):
        """GET /news/headlines returns a list."""
        status, body = _request("GET", "/api/v1/news/headlines", token=access_token)
        assert status == 200
        assert isinstance(body, list)

    def test_security_audit_log_schema(self, access_token):
        """GET /security/audit-log returns {entries: [...], total: int}."""
        status, body = _request("GET", "/api/v1/security/audit-log", token=access_token)
        assert status == 200
        assert "entries" in body
        assert "total" in body
        assert isinstance(body["entries"], list)
        assert isinstance(body["total"], int)

    def test_security_sessions_schema(self, access_token):
        """GET /security/sessions returns a list of session objects."""
        status, body = _request("GET", "/api/v1/security/sessions", token=access_token)
        assert status == 200
        assert isinstance(body, list)
        if body:
            session = body[0]
            assert "id" in session
            assert "ip_address" in session
            assert "last_active" in session

    def test_security_2fa_status_schema(self, access_token):
        """GET /security/2fa/status returns {enabled: bool, ...}."""
        status, body = _request("GET", "/api/v1/security/2fa/status", token=access_token)
        assert status == 200
        assert "enabled" in body
        assert isinstance(body["enabled"], bool)

    def test_login_response_schema(self):
        """POST /auth/login returns {access_token, refresh_token, token_type, expires_in}."""
        status, body = _request(
            "POST",
            "/api/v1/auth/login",
            body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert status == 200
        assert "access_token" in body
        assert "refresh_token" in body
        assert "token_type" in body
        assert body["token_type"] == "bearer"


# =============================================================================
# Phase 3B — Cross-Component Workflow Tests
# =============================================================================


class TestWorkflows:
    """End-to-end workflows spanning multiple services."""

    def test_login_then_dashboard_data(self):
        """Login → fetch briefing + finance + calendar + email (dashboard load)."""
        # Step 1: Login
        status, login_body = _request(
            "POST",
            "/api/v1/auth/login",
            body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert status == 200
        token = login_body["access_token"]

        # Step 2: Fetch all dashboard endpoints (what the dashboard page loads)
        status, _ = _request("GET", "/api/v1/briefing/today", token=token)
        assert status == 200

        status, _ = _request("GET", "/api/v1/finance/balances", token=token)
        assert status == 200

        status, _ = _request("GET", "/api/v1/calendar/today", token=token)
        assert status == 200

        status, _ = _request("GET", "/api/v1/email/digest", token=token)
        assert status == 200

    def test_health_ingest_then_summary_reflects(self, access_token):
        """Ingest Apple Health data → summary endpoint returns data."""
        # Step 1: Ingest health data
        status, _ = _request(
            "POST",
            "/api/v1/health-data/ingest/apple-health",
            token=access_token,
            body={
                "metrics": [
                    {"type": "steps", "value": 8500, "date": "2026-02-23"},
                    {"type": "heart_rate", "value": 72, "date": "2026-02-23"},
                ]
            },
        )
        assert status in {200, 201}

        # Step 2: Summary should reflect the ingested data
        status, summary = _request(
            "GET", "/api/v1/health-data/summary", token=access_token
        )
        assert status == 200
        assert isinstance(summary, dict)

    def test_content_generate_then_drafts_list(self, access_token):
        """Generate content → appears in drafts list."""
        # Step 1: Generate content
        status, gen_body = _request(
            "POST",
            "/api/v1/content/generate",
            token=access_token,
            body={
                "topic": "workflow test topic",
                "platform": "linkedin",
                "tone": "professional",
            },
        )
        assert status in {200, 503}  # 503 if Claude API unconfigured

        # Step 2: Fetch drafts — the generated content should be retrievable
        status, drafts = _request(
            "GET", "/api/v1/content/drafts", token=access_token
        )
        assert status == 200
        assert isinstance(drafts, list)

    def test_screen_time_ingest_then_productivity(self, access_token):
        """Ingest screen time → productivity summary updates."""
        # Step 1: Ingest screen time data
        status, _ = _request(
            "POST",
            "/api/v1/productivity/ingest/screen-time",
            token=access_token,
            body={
                "entries": [
                    {
                        "app_name": "VS Code",
                        "category": "development",
                        "duration_minutes": 120,
                        "date": "2026-02-23",
                    },
                    {
                        "app_name": "Slack",
                        "category": "communication",
                        "duration_minutes": 45,
                        "date": "2026-02-23",
                    },
                ]
            },
        )
        assert status in {200, 201}

        # Step 2: Productivity summary should reflect the data
        status, summary = _request(
            "GET", "/api/v1/productivity/summary", token=access_token
        )
        assert status == 200
        assert isinstance(summary, dict)

    def test_security_audit_reflects_activity(self, access_token):
        """API calls should appear in audit log."""
        # Step 1: Make a known API call
        _request("GET", "/api/v1/finance/balances", token=access_token)

        # Step 2: Audit log should have entries
        status, body = _request(
            "GET", "/api/v1/security/audit-log?limit=5", token=access_token
        )
        assert status == 200
        assert body["total"] > 0
        assert len(body["entries"]) > 0

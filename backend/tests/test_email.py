"""Tests for email integration, LMS clients, and assignment tracker."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Email categorization tests
# ---------------------------------------------------------------------------


def test_heuristic_categorize_academic():
    """Academic emails are classified correctly."""
    from app.services.email_analyzer import _heuristic_categorize

    assert _heuristic_categorize("Assignment Due Tomorrow", "canvas@drexel.edu", "") == "academic"
    assert _heuristic_categorize("Grade Posted", "blackboard@drexel.edu", "") == "academic"
    assert _heuristic_categorize("Quiz Available", "instructor@school.edu", "") == "academic"


def test_heuristic_categorize_priority():
    """Priority emails are classified correctly."""
    from app.services.email_analyzer import _heuristic_categorize

    assert _heuristic_categorize("URGENT: Action Required", "boss@company.com", "") == "priority"
    assert _heuristic_categorize("Important Deadline", "team@work.com", "") == "priority"


def test_heuristic_categorize_promotional():
    """Promotional emails are classified correctly."""
    from app.services.email_analyzer import _heuristic_categorize

    result = _heuristic_categorize(
        "50% Off Sale",
        "deals@store.com",
        "Click to unsubscribe from our newsletter",
    )
    assert result == "promotional"


def test_heuristic_categorize_junk():
    """Junk emails are classified correctly."""
    from app.services.email_analyzer import _heuristic_categorize

    assert _heuristic_categorize("Update", "noreply@service.com", "") == "junk"
    assert _heuristic_categorize("Info", "no-reply@alerts.com", "") == "junk"


def test_heuristic_categorize_informational():
    """Default emails are classified as informational."""
    from app.services.email_analyzer import _heuristic_categorize

    assert _heuristic_categorize("Meeting Notes", "colleague@company.com", "") == "informational"


# ---------------------------------------------------------------------------
# Gmail body extraction tests
# ---------------------------------------------------------------------------


def test_extract_body_plaintext():
    """Extract body from a plaintext Gmail payload."""
    import base64

    from app.integrations.gmail_client import _extract_body

    body_text = "Hello, this is a test email."
    encoded = base64.urlsafe_b64encode(body_text.encode()).decode()

    payload = {
        "mimeType": "text/plain",
        "body": {"data": encoded},
    }
    result = _extract_body(payload)
    assert result == body_text


def test_extract_body_multipart():
    """Extract body from a multipart Gmail payload."""
    import base64

    from app.integrations.gmail_client import _extract_body

    body_text = "Nested body content."
    encoded = base64.urlsafe_b64encode(body_text.encode()).decode()

    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": encoded},
            },
            {
                "mimeType": "text/html",
                "body": {"data": ""},
            },
        ],
    }
    result = _extract_body(payload)
    assert result == body_text


def test_extract_body_empty():
    """Empty payload returns empty string."""
    from app.integrations.gmail_client import _extract_body

    assert _extract_body({}) == ""
    assert _extract_body({"mimeType": "text/plain", "body": {}}) == ""


# ---------------------------------------------------------------------------
# Canvas client tests
# ---------------------------------------------------------------------------


def test_infer_assignment_type():
    """Canvas assignment type inference from submission types."""
    from app.integrations.canvas_client import _infer_type

    assert _infer_type(["online_quiz"]) == "quiz"
    assert _infer_type(["discussion_topic"]) == "discussion"
    assert _infer_type(["online_upload"]) == "upload"
    assert _infer_type(["external_tool"]) == "external"
    assert _infer_type(["online_text_entry"]) == "homework"
    assert _infer_type([]) == "homework"


# ---------------------------------------------------------------------------
# Schwab account masking (regression)
# ---------------------------------------------------------------------------


def test_plaid_frequency_classification():
    """Plaid recurring frequency classification regression."""
    from app.integrations.plaid_client import _classify_frequency

    assert _classify_frequency(30) == "monthly"
    assert _classify_frequency(7) == "weekly"


# ---------------------------------------------------------------------------
# Assignment tracker tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assignment_tracker_imports():
    """Assignment tracker service modules import correctly."""
    from app.services.assignment_tracker import (
        generate_reminders,
        get_overdue_assignments,
        get_upcoming_assignments,
    )

    assert callable(get_upcoming_assignments)
    assert callable(get_overdue_assignments)
    assert callable(generate_reminders)


@pytest.mark.asyncio
async def test_email_analyzer_imports():
    """Email analyzer service modules import correctly."""
    from app.services.email_analyzer import (
        daily_email_digest,
        spam_audit,
        weekly_email_digest,
    )

    assert callable(daily_email_digest)
    assert callable(spam_audit)
    assert callable(weekly_email_digest)


# ---------------------------------------------------------------------------
# GmailClient import and structure tests
# ---------------------------------------------------------------------------


def test_gmail_client_import():
    """GmailClient can be imported from the integrations module."""
    from app.integrations.gmail_client import GmailClient

    assert GmailClient is not None


def test_gmail_client_is_base_integration():
    """GmailClient inherits from BaseIntegration."""
    from app.integrations.base import BaseIntegration
    from app.integrations.gmail_client import GmailClient

    assert issubclass(GmailClient, BaseIntegration)


def test_gmail_client_has_required_methods():
    """GmailClient has sync, health_check, and email fetching methods."""
    from app.integrations.gmail_client import GmailClient

    assert hasattr(GmailClient, "sync")
    assert hasattr(GmailClient, "health_check")
    assert hasattr(GmailClient, "fetch_new_emails")
    assert hasattr(GmailClient, "get_email_body")
    assert hasattr(GmailClient, "list_labels")
    assert hasattr(GmailClient, "store_email")


# ---------------------------------------------------------------------------
# Email categorization edge cases
# ---------------------------------------------------------------------------


def test_heuristic_categorize_case_insensitive():
    """Email categorization is case-insensitive for subjects and senders."""
    from app.services.email_analyzer import _heuristic_categorize

    assert _heuristic_categorize("URGENT meeting", "boss@co.com", "") == "priority"
    assert _heuristic_categorize("Assignment Due", "CANVAS@DREXEL.EDU", "") == "academic"


def test_heuristic_categorize_snippet_promo():
    """Promotional classification works via snippet content."""
    from app.services.email_analyzer import _heuristic_categorize

    result = _heuristic_categorize(
        "Weekly Update",
        "info@store.com",
        "Click here to unsubscribe from our mailing list",
    )
    assert result == "promotional"


# ---------------------------------------------------------------------------
# Email analyzer service tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_categorize_email_fallback():
    """categorize_email falls back to heuristics when no API key."""
    from unittest.mock import AsyncMock

    from app.services.email_analyzer import categorize_email

    mock_db = AsyncMock()
    email_data = {
        "subject": "Assignment Due Tomorrow",
        "sender": "canvas@drexel.edu",
        "snippet": "",
    }

    result = await categorize_email(mock_db, "fake-user", email_data)
    assert result == "academic"


@pytest.mark.asyncio
async def test_daily_email_digest_empty():
    """daily_email_digest returns correct structure when no emails exist."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.email_analyzer import daily_email_digest

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock the query to return empty results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    with patch("app.services.email_analyzer.audit_log", new_callable=AsyncMock):
        result = await daily_email_digest(mock_db, user_id)

    assert "date" in result
    assert "total_emails" in result
    assert "by_category" in result
    assert result["total_emails"] == 0
    assert "priority" in result["by_category"]
    assert "academic" in result["by_category"]


@pytest.mark.asyncio
async def test_spam_audit_empty():
    """spam_audit returns empty list when no spam/promo emails found."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock

    from app.services.email_analyzer import spam_audit

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock query to return empty results
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    mock_db.execute.return_value = mock_result

    result = await spam_audit(mock_db, user_id)
    assert isinstance(result, list)
    assert len(result) == 0


def test_email_categories_constant():
    """The CATEGORIES tuple contains the expected categories."""
    from app.services.email_analyzer import CATEGORIES

    assert "priority" in CATEGORIES
    assert "informational" in CATEGORIES
    assert "promotional" in CATEGORIES
    assert "junk" in CATEGORIES
    assert "academic" in CATEGORIES

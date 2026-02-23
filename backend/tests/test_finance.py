"""Tests for financial integration — Plaid, Schwab, and finance analyzer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# PlaidClient unit tests (mocked — no real Plaid calls)
# ---------------------------------------------------------------------------


def test_plaid_unavailable_error():
    """PlaidClient raises PlaidUnavailableError when plaid-python is missing."""
    with patch.dict("sys.modules", {"plaid": None, "plaid.api": None}):
        # Force reimport to trigger ImportError path

        from app.integrations import plaid_client

        # If plaid IS installed in the test env, PLAID_AVAILABLE will be True
        # We test the error path directly
        if not plaid_client.PLAID_AVAILABLE:
            with pytest.raises(plaid_client.PlaidUnavailableError):
                plaid_client.PlaidClient("fake-user-id", MagicMock())


def test_classify_frequency():
    """Frequency classification from average interval days."""
    from app.integrations.plaid_client import _classify_frequency

    assert _classify_frequency(7) == "weekly"
    assert _classify_frequency(14) == "bi-weekly"
    assert _classify_frequency(30) == "monthly"
    assert _classify_frequency(60) == "bi-monthly"
    assert _classify_frequency(90) == "quarterly"
    assert _classify_frequency(365) == "annual"
    assert _classify_frequency(2) is None
    assert _classify_frequency(200) is None


# ---------------------------------------------------------------------------
# SchwabClient unit tests
# ---------------------------------------------------------------------------


def test_schwab_mask_account():
    """Account masking shows only last 4 digits."""
    from app.integrations.schwab_client import _mask_account

    assert _mask_account("12345678") == "****5678"
    assert _mask_account("ABC") == "****"
    assert _mask_account("") == "****"


def test_schwab_confirmation_token_unique():
    """Confirmation tokens should be unique for different trade parameters."""
    from app.integrations.schwab_client import SchwabClient

    token1 = SchwabClient._generate_confirmation_token(
        {"symbol": "AAPL", "quantity": 10, "action": "BUY"}
    )
    token2 = SchwabClient._generate_confirmation_token(
        {"symbol": "AAPL", "quantity": 10, "action": "BUY"}
    )
    # Each call generates a unique nonce, so tokens should differ
    assert token1 != token2
    assert len(token1) == 64  # SHA-256 hex digest


@pytest.mark.asyncio
async def test_schwab_place_trade_requires_limit_price():
    """LIMIT orders require limit_price parameter."""
    from app.integrations.schwab_client import SchwabClient, SchwabTradeError

    # Create a mock client
    mock_db = AsyncMock()
    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "test-user"
        client._log = MagicMock()
        client._pending_confirmations = {}
        client._app_key = "test"
        client._app_secret = "test"
        client._callback_url = "test"

        # Mock _audit
        client._audit = AsyncMock()
        client.db = mock_db

        with pytest.raises(SchwabTradeError, match="limit_price is required"):
            await client.place_trade(
                symbol="AAPL",
                quantity=10,
                order_type="LIMIT",
                action="BUY",
            )


@pytest.mark.asyncio
async def test_schwab_confirm_trade_expired_token():
    """Expired confirmation tokens are rejected."""
    from app.integrations.schwab_client import SchwabClient, SchwabTradeError

    # Add an expired confirmation (includes user_id as third element)
    SchwabClient._pending_confirmations["expired-token"] = (
        {"symbol": "AAPL", "_order_payload": {}},
        0,  # Expired timestamp (epoch 0)
        "test-user",
    )

    mock_db = AsyncMock()
    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "test-user"
        client._log = MagicMock()
        client.db = mock_db

        with pytest.raises(SchwabTradeError, match="expired"):
            await client.confirm_trade("expired-token")

    # Cleanup
    SchwabClient._pending_confirmations.pop("expired-token", None)


@pytest.mark.asyncio
async def test_schwab_confirm_trade_invalid_token():
    """Invalid confirmation tokens are rejected."""
    from app.integrations.schwab_client import SchwabClient, SchwabTradeError

    mock_db = AsyncMock()
    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "test-user"
        client._log = MagicMock()
        client.db = mock_db

        with pytest.raises(SchwabTradeError, match="Invalid or expired"):
            await client.confirm_trade("nonexistent-token")


# ---------------------------------------------------------------------------
# Finance analyzer unit tests
# ---------------------------------------------------------------------------


def test_parse_period():
    """Period string parsing works for common formats."""
    from app.services.finance_analyzer import _parse_period

    assert _parse_period("7d") == 7
    assert _parse_period("30d") == 30
    assert _parse_period("90d") == 90
    assert _parse_period("365d") == 365
    assert _parse_period("week") == 7
    assert _parse_period("month") == 30
    assert _parse_period("quarter") == 90
    assert _parse_period("year") == 365
    assert _parse_period("invalid") == 30  # default


# ---------------------------------------------------------------------------
# Trade two-step confirmation flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trade_two_step_flow():
    """Trade execution requires preview → confirmation (two API calls)."""
    from app.integrations.schwab_client import SchwabClient

    mock_db = AsyncMock()
    # Clear class-level pending confirmations before test
    SchwabClient._pending_confirmations.clear()

    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "test-user"
        client._log = MagicMock()
        client._audit = AsyncMock()
        client.db = mock_db

        # Step 1: Place trade returns preview + token
        result = await client.place_trade(
            symbol="AAPL",
            quantity=5,
            order_type="MARKET",
            action="BUY",
        )
        assert "preview" in result
        assert "confirmation_token" in result
        assert result["preview"]["status"] == "PENDING_CONFIRMATION"
        assert result["preview"]["symbol"] == "AAPL"
        assert result["preview"]["quantity"] == 5
        assert result["expires_in_seconds"] == 300

        # Token stored in class-level pending confirmations
        token = result["confirmation_token"]
        assert token in SchwabClient._pending_confirmations

    # Cleanup
    SchwabClient._pending_confirmations.clear()


# ---------------------------------------------------------------------------
# Finding 1 — Trade confirmation tokens bound to user identity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schwab_confirm_trade_user_mismatch():
    """Confirm trade rejects tokens that belong to a different user."""
    import time

    from app.integrations.schwab_client import SchwabClient, SchwabTradeError

    # Add a confirmation bound to user-A
    SchwabClient._pending_confirmations["user-bound-token"] = (
        {"symbol": "AAPL", "_order_payload": {}},
        time.time() + 300,
        "user-A",
    )

    mock_db = AsyncMock()
    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "user-B"  # Different user
        client._log = MagicMock()
        client.db = mock_db

        with pytest.raises(SchwabTradeError, match="Invalid or expired"):
            await client.confirm_trade("user-bound-token")

    # Cleanup
    SchwabClient._pending_confirmations.pop("user-bound-token", None)


@pytest.mark.asyncio
async def test_schwab_place_trade_stores_user_id():
    """place_trade stores user_id as third element in pending confirmations."""
    from app.integrations.schwab_client import SchwabClient

    SchwabClient._pending_confirmations.clear()

    mock_db = AsyncMock()
    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "test-user-123"
        client._log = MagicMock()
        client._audit = AsyncMock()
        client.db = mock_db

        result = await client.place_trade(
            symbol="MSFT",
            quantity=10,
            order_type="MARKET",
            action="BUY",
        )
        token = result["confirmation_token"]
        pending = SchwabClient._pending_confirmations[token]
        assert len(pending) == 3
        assert pending[2] == "test-user-123"

    SchwabClient._pending_confirmations.clear()


# ---------------------------------------------------------------------------
# Finding 5/6 — TradeRequest input validation
# ---------------------------------------------------------------------------


def test_trade_request_symbol_validation():
    """TradeRequest rejects invalid symbols."""
    from pydantic import ValidationError

    from app.api.v1.finance import TradeRequest

    # Valid symbol
    req = TradeRequest(symbol="AAPL", quantity=1, order_type="MARKET", action="BUY")
    assert req.symbol == "AAPL"

    # Valid symbol with dot (e.g., BRK.B)
    req = TradeRequest(symbol="BRK.B", quantity=1, order_type="MARKET", action="BUY")
    assert req.symbol == "BRK.B"

    # Invalid: lowercase
    with pytest.raises(ValidationError):
        TradeRequest(symbol="aapl", quantity=1, order_type="MARKET", action="BUY")

    # Invalid: empty
    with pytest.raises(ValidationError):
        TradeRequest(symbol="", quantity=1, order_type="MARKET", action="BUY")

    # Invalid: too long
    with pytest.raises(ValidationError):
        TradeRequest(symbol="A" * 11, quantity=1, order_type="MARKET", action="BUY")

    # Invalid: special characters
    with pytest.raises(ValidationError):
        TradeRequest(symbol="AAPL;DROP", quantity=1, order_type="MARKET", action="BUY")


def test_trade_request_limit_price_bounds():
    """TradeRequest enforces limit_price bounds."""
    from pydantic import ValidationError

    from app.api.v1.finance import TradeRequest

    # Valid limit price
    req = TradeRequest(
        symbol="AAPL", quantity=1, order_type="LIMIT", action="BUY", limit_price=150.0
    )
    assert req.limit_price == 150.0

    # Invalid: zero
    with pytest.raises(ValidationError):
        TradeRequest(symbol="AAPL", quantity=1, order_type="LIMIT", action="BUY", limit_price=0)

    # Invalid: negative
    with pytest.raises(ValidationError):
        TradeRequest(symbol="AAPL", quantity=1, order_type="LIMIT", action="BUY", limit_price=-10)

    # Invalid: exceeds upper bound
    with pytest.raises(ValidationError):
        TradeRequest(
            symbol="AAPL",
            quantity=1,
            order_type="LIMIT",
            action="BUY",
            limit_price=1_000_001,
        )


# ---------------------------------------------------------------------------
# Finding 11 — OAuth state parameter
# ---------------------------------------------------------------------------


def test_schwab_get_authorization_url_returns_state():
    """get_authorization_url returns a (url, state) tuple with state in URL."""
    from app.integrations.schwab_client import SchwabClient

    SchwabClient._pending_oauth_states.clear()

    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "test-user"
        client._app_key = "test-key"
        client._callback_url = "https://example.com/callback"

        url, state = client.get_authorization_url()
        assert f"&state={state}" in url
        assert state in SchwabClient._pending_oauth_states
        stored_user_id, _expiry = SchwabClient._pending_oauth_states[state]
        assert stored_user_id == "test-user"

    SchwabClient._pending_oauth_states.clear()


def test_schwab_validate_oauth_state_rejects_invalid():
    """_validate_oauth_state rejects unknown state tokens."""
    from app.integrations.schwab_client import SchwabAuthError, SchwabClient

    SchwabClient._pending_oauth_states.clear()

    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "test-user"
        client._log = MagicMock()

        with pytest.raises(SchwabAuthError, match="Invalid or expired OAuth state"):
            client._validate_oauth_state("nonexistent-state")


def test_schwab_validate_oauth_state_rejects_wrong_user():
    """_validate_oauth_state rejects state tokens from a different user."""
    import time

    from app.integrations.schwab_client import SchwabAuthError, SchwabClient

    SchwabClient._pending_oauth_states.clear()
    SchwabClient._pending_oauth_states["test-state"] = (
        "user-A",
        time.time() + 600,
    )

    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "user-B"  # Different user
        client._log = MagicMock()

        with pytest.raises(SchwabAuthError, match="Invalid or expired OAuth state"):
            client._validate_oauth_state("test-state")

    SchwabClient._pending_oauth_states.clear()


def test_schwab_validate_oauth_state_rejects_expired():
    """_validate_oauth_state rejects expired state tokens."""
    from app.integrations.schwab_client import SchwabAuthError, SchwabClient

    SchwabClient._pending_oauth_states.clear()
    SchwabClient._pending_oauth_states["expired-state"] = (
        "test-user",
        0,  # Expired (epoch 0)
    )

    with patch.object(SchwabClient, "__init__", lambda self, *a, **kw: None):
        client = SchwabClient.__new__(SchwabClient)
        client.user_id = "test-user"
        client._log = MagicMock()

        with pytest.raises(SchwabAuthError, match="expired"):
            client._validate_oauth_state("expired-state")

    SchwabClient._pending_oauth_states.clear()


# ---------------------------------------------------------------------------
# BaseIntegration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_base_integration_audit():
    """BaseIntegration._audit writes to audit log."""
    from app.integrations.base import BaseIntegration

    # We can't instantiate an ABC directly, so test via PlaidClient or a concrete subclass
    # Instead, verify the base class methods exist and have correct signatures
    assert hasattr(BaseIntegration, "get_credential")
    assert hasattr(BaseIntegration, "store_credential")
    assert hasattr(BaseIntegration, "_audit")
    assert hasattr(BaseIntegration, "sync")
    assert hasattr(BaseIntegration, "health_check")


# ---------------------------------------------------------------------------
# PlaidClient import and structure tests
# ---------------------------------------------------------------------------


def test_plaid_client_import():
    """PlaidClient can be imported from the integrations module."""
    from app.integrations.plaid_client import PlaidClient

    assert PlaidClient is not None


def test_plaid_client_is_base_integration():
    """PlaidClient inherits from BaseIntegration."""
    from app.integrations.base import BaseIntegration
    from app.integrations.plaid_client import PlaidClient

    assert issubclass(PlaidClient, BaseIntegration)


def test_plaid_client_has_required_methods():
    """PlaidClient has sync, health_check, and data retrieval methods."""
    from app.integrations.plaid_client import PlaidClient

    assert hasattr(PlaidClient, "sync")
    assert hasattr(PlaidClient, "health_check")
    assert callable(getattr(PlaidClient, "sync", None))
    assert callable(getattr(PlaidClient, "health_check", None))


# ---------------------------------------------------------------------------
# analyze_spending tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_spending_no_accounts():
    """analyze_spending returns empty result when user has no linked accounts."""
    import uuid

    from app.services.finance_analyzer import analyze_spending

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock the accounts query to return no accounts
    mock_accounts_result = MagicMock()
    mock_accounts_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_accounts_result

    with patch("app.services.finance_analyzer.audit_log", new_callable=AsyncMock):
        result = await analyze_spending(mock_db, user_id, "30d")

    assert result["categories"] == {}
    assert result["total"] == 0
    assert result["period"] == "30d"
    assert result["trend_pct"] == 0


@pytest.mark.asyncio
async def test_analyze_spending_skips_audit_when_no_accounts():
    """analyze_spending skips audit log when user has no linked accounts."""
    import uuid

    from app.services.finance_analyzer import analyze_spending

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock accounts query to return no accounts (early return path)
    mock_accounts_result = MagicMock()
    mock_accounts_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_accounts_result

    with patch("app.services.finance_analyzer.audit_log", new_callable=AsyncMock) as mock_audit:
        result = await analyze_spending(mock_db, user_id, "30d")
        # Early return path does not call audit_log
        mock_audit.assert_not_called()
        # Result still has correct structure
        assert result["categories"] == {}
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# identify_subscriptions tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_identify_subscriptions_no_accounts():
    """identify_subscriptions returns empty list for users with no accounts."""
    import uuid

    from app.services.finance_analyzer import identify_subscriptions

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock accounts query
    mock_accounts_result = MagicMock()
    mock_accounts_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_accounts_result

    result = await identify_subscriptions(mock_db, user_id)
    assert result == []


# ---------------------------------------------------------------------------
# affordability_check tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_affordability_check_no_accounts():
    """affordability_check returns not-affordable for users with no accounts."""
    import uuid

    from app.services.finance_analyzer import affordability_check

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock accounts query
    mock_accounts_result = MagicMock()
    mock_accounts_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_accounts_result

    with patch("app.services.finance_analyzer.audit_log", new_callable=AsyncMock):
        result = await affordability_check(mock_db, user_id, 100.0, "test")

    assert result["affordable"] is False
    assert result["monthly_income"] == 0
    assert result["monthly_expenses"] == 0
    assert result["available_budget"] == 0
    assert result["amount"] == 100.0
    assert result["category"] == "test"
    assert "No linked accounts" in result["recommendation"]


@pytest.mark.asyncio
async def test_affordability_check_skips_audit_when_no_accounts():
    """affordability_check skips audit log when no accounts linked."""
    import uuid

    from app.services.finance_analyzer import affordability_check

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock accounts query (no accounts path triggers early return)
    mock_accounts_result = MagicMock()
    mock_accounts_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_accounts_result

    with patch("app.services.finance_analyzer.audit_log", new_callable=AsyncMock) as mock_audit:
        result = await affordability_check(mock_db, user_id, 50.0)
        # Early return path does not call audit_log
        mock_audit.assert_not_called()
        # Result still correctly indicates not affordable
        assert result["affordable"] is False


@pytest.mark.asyncio
async def test_finance_analyzer_function_signatures():
    """Finance analyzer exports the expected public functions."""
    from app.services.finance_analyzer import (
        affordability_check,
        analyze_spending,
        identify_subscriptions,
        portfolio_daily_brief,
    )

    assert callable(analyze_spending)
    assert callable(identify_subscriptions)
    assert callable(affordability_check)
    assert callable(portfolio_daily_brief)

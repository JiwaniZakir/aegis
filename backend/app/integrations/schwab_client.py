"""Schwab integration — portfolio management and trade execution via direct HTTP."""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from decimal import Decimal

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration

logger = structlog.get_logger()

# Schwab API base URLs
_SCHWAB_AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
_SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"  # noqa: S105
_SCHWAB_API_BASE = "https://api.schwabapi.com/trader/v1"

# Trade confirmation tokens expire after 5 minutes
_CONFIRMATION_TTL_SECONDS = 300


class SchwabAuthError(Exception):
    """Raised when Schwab OAuth authentication fails."""


class SchwabTradeError(Exception):
    """Raised when a trade operation fails."""


class TradeConfirmationRequiredError(Exception):
    """Raised when a trade preview has been generated and requires confirmation."""

    def __init__(self, preview: dict, confirmation_token: str) -> None:
        self.preview = preview
        self.confirmation_token = confirmation_token
        super().__init__("Trade requires confirmation before execution.")


class SchwabClient(BaseIntegration):
    """Integration client for Schwab/Fidelity brokerage APIs.

    Uses direct HTTP calls via httpx.AsyncClient (no schwab-py library).
    Trade execution requires a TWO-STEP confirmation process:
    1. ``place_trade()`` returns a preview + confirmation_token
    2. ``confirm_trade()`` with the token executes the order
    """

    # In-memory store for pending trade confirmations.
    # Maps confirmation_token -> (preview_data, expiry_timestamp, user_id)
    _pending_confirmations: dict[str, tuple[dict, float, str]] = {}

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._app_key = settings.schwab_app_key
        self._app_secret = settings.schwab_app_secret
        self._callback_url = settings.schwab_callback_url

    # In-memory store for pending OAuth state tokens.
    # Maps state_token -> (user_id, expiry_timestamp)
    _pending_oauth_states: dict[str, tuple[str, float]] = {}

    # OAuth state tokens expire after 10 minutes
    _OAUTH_STATE_TTL_SECONDS = 600

    # ------------------------------------------------------------------
    # OAuth flow
    # ------------------------------------------------------------------

    def get_authorization_url(self) -> tuple[str, str]:
        """Generate the Schwab OAuth authorization URL for user consent.

        Returns:
            Tuple of (authorization_url, state_token). The state token must
            be validated in the callback to prevent CSRF attacks.
        """
        state = secrets.token_urlsafe(32)
        self._pending_oauth_states[state] = (
            self.user_id,
            time.time() + self._OAUTH_STATE_TTL_SECONDS,
        )
        url = (
            f"{_SCHWAB_AUTH_URL}"
            f"?client_id={self._app_key}"
            f"&redirect_uri={self._callback_url}"
            f"&response_type=code"
            f"&state={state}"
        )
        return url, state

    def _validate_oauth_state(self, state: str) -> None:
        """Validate and consume an OAuth state token.

        Raises:
            SchwabAuthError: If the state is invalid, expired, or belongs to
                a different user.
        """
        pending = self._pending_oauth_states.pop(state, None)
        if pending is None:
            msg = "Invalid or expired OAuth state parameter"
            raise SchwabAuthError(msg)

        state_user_id, expiry = pending
        if state_user_id != self.user_id:
            self._log.warning(
                "schwab_oauth_state_user_mismatch",
                expected_user=state_user_id,
                actual_user=self.user_id,
            )
            msg = "Invalid or expired OAuth state parameter"
            raise SchwabAuthError(msg)
        if time.time() > expiry:
            msg = "OAuth state parameter has expired"
            raise SchwabAuthError(msg)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def authenticate(self, authorization_code: str, *, state: str) -> dict:
        """Exchange an OAuth authorization code for access and refresh tokens.

        Tokens are encrypted and stored in the credentials table.

        Args:
            authorization_code: The code returned by Schwab OAuth redirect.
            state: The OAuth state parameter returned in the callback. Must
                match a previously issued state from ``get_authorization_url()``.

        Returns:
            dict with token_type, expires_in (no raw tokens exposed).

        Raises:
            SchwabAuthError: If state validation fails or token exchange fails.
        """
        self._validate_oauth_state(state)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    _SCHWAB_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": authorization_code,
                        "redirect_uri": self._callback_url,
                        "client_id": self._app_key,
                        "client_secret": self._app_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                data = response.json()

            # Store tokens encrypted
            await self.store_credential("schwab_access_token", data["access_token"])
            await self.store_credential("schwab_refresh_token", data["refresh_token"])

            self._log.info("schwab_authenticated")
            await self._audit(
                action="schwab_authenticate",
                resource_type="schwab",
            )

            return {
                "token_type": data.get("token_type", "Bearer"),
                "expires_in": data.get("expires_in", 1800),
            }

        except httpx.HTTPStatusError as exc:
            self._log.error(
                "schwab_auth_failed",
                status_code=exc.response.status_code,
            )
            msg = f"Schwab authentication failed: {exc.response.status_code}"
            raise SchwabAuthError(msg) from exc
        except httpx.HTTPError as exc:
            self._log.error("schwab_auth_network_error", error=str(type(exc).__name__))
            raise

    async def _refresh_access_token(self) -> str:
        """Refresh the Schwab access token using the stored refresh token.

        Returns:
            The new access token (also stored encrypted).
        """
        refresh_token = await self.get_credential("schwab_refresh_token")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                _SCHWAB_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self._app_key,
                    "client_secret": self._app_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        await self.store_credential("schwab_access_token", data["access_token"])
        if "refresh_token" in data:
            await self.store_credential("schwab_refresh_token", data["refresh_token"])

        self._log.debug("schwab_token_refreshed")
        return data["access_token"]

    async def _get_access_token(self) -> str:
        """Get the current access token, refreshing if needed."""
        try:
            return await self.get_credential("schwab_access_token")
        except KeyError:
            self._log.warning("schwab_no_access_token_attempting_refresh")
            return await self._refresh_access_token()

    async def _api_request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated request to the Schwab API.

        Automatically retries once with a refreshed token on 401.
        """
        access_token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{_SCHWAB_API_BASE}{path}"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=json,
                params=params,
            )

            # Retry once with refreshed token on 401
            if response.status_code == 401:
                access_token = await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {access_token}"
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    params=params,
                )

            response.raise_for_status()
            return response.json() if response.content else {}

    # ------------------------------------------------------------------
    # Portfolio
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_portfolio(self) -> dict:
        """Fetch current positions and account balances from Schwab.

        Returns:
            dict with accounts, positions, and total values.
        """
        try:
            data = await self._api_request("GET", "/accounts")
            accounts_data = data if isinstance(data, list) else data.get("accounts", [])

            portfolio = {
                "accounts": [],
                "total_value": Decimal("0"),
            }

            for acct in accounts_data:
                acct_info = acct.get("securitiesAccount", acct)
                positions = []
                for pos in acct_info.get("positions", []):
                    instrument = pos.get("instrument", {})
                    positions.append(
                        {
                            "symbol": instrument.get("symbol", ""),
                            "quantity": pos.get("longQuantity", 0),
                            "market_value": pos.get("marketValue", 0),
                            "average_price": pos.get("averagePrice", 0),
                            "current_price": pos.get("currentDayProfitLoss", 0),
                            "asset_type": instrument.get("assetType", "EQUITY"),
                        }
                    )

                account_value = Decimal(
                    str(acct_info.get("currentBalances", {}).get("liquidationValue", 0))
                )
                portfolio["accounts"].append(
                    {
                        "account_number_masked": _mask_account(acct_info.get("accountNumber", "")),
                        "type": acct_info.get("type", ""),
                        "value": float(account_value),
                        "positions": positions,
                    }
                )
                portfolio["total_value"] += account_value

            portfolio["total_value"] = float(portfolio["total_value"])

            self._log.info(
                "schwab_portfolio_fetched",
                account_count=len(portfolio["accounts"]),
            )
            await self._audit(
                action="schwab_portfolio_fetch",
                resource_type="portfolio",
                metadata={"account_count": len(portfolio["accounts"])},
            )
            return portfolio

        except httpx.HTTPStatusError as exc:
            self._log.error(
                "schwab_portfolio_failed",
                status_code=exc.response.status_code,
            )
            raise
        except Exception as exc:
            self._log.error("schwab_portfolio_error", error=str(type(exc).__name__))
            raise

    # ------------------------------------------------------------------
    # Transaction history
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_transactions(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Fetch trade history from Schwab.

        Args:
            start_date: ISO date string (YYYY-MM-DD). Defaults to 30 days ago.
            end_date: ISO date string (YYYY-MM-DD). Defaults to today.

        Returns:
            List of transaction dicts.
        """
        from datetime import date, timedelta

        if start_date is None:
            start_date = (date.today() - timedelta(days=30)).isoformat()
        if end_date is None:
            end_date = date.today().isoformat()

        try:
            data = await self._api_request(
                "GET",
                "/accounts/transactions",
                params={
                    "startDate": start_date,
                    "endDate": end_date,
                    "types": "TRADE",
                },
            )

            transactions = []
            raw_txns = data if isinstance(data, list) else data.get("transactions", [])
            for txn in raw_txns:
                transactions.append(
                    {
                        "id": txn.get("transactionId", ""),
                        "date": txn.get("transactionDate", ""),
                        "type": txn.get("type", ""),
                        "description": txn.get("description", ""),
                        "amount": txn.get("netAmount", 0),
                        "symbol": txn.get("transferItems", [{}])[0]
                        .get("instrument", {})
                        .get("symbol", "")
                        if txn.get("transferItems")
                        else "",
                    }
                )

            self._log.info("schwab_transactions_fetched", count=len(transactions))
            await self._audit(
                action="schwab_transaction_fetch",
                resource_type="trade",
                metadata={"count": len(transactions)},
            )
            return transactions

        except httpx.HTTPStatusError as exc:
            self._log.error(
                "schwab_transactions_failed",
                status_code=exc.response.status_code,
            )
            raise
        except Exception as exc:
            self._log.error("schwab_transactions_error", error=str(type(exc).__name__))
            raise

    # ------------------------------------------------------------------
    # Trade execution — TWO-STEP CONFIRMATION
    # ------------------------------------------------------------------

    async def place_trade(
        self,
        symbol: str,
        quantity: int,
        order_type: str,
        action: str,
        *,
        limit_price: float | None = None,
    ) -> dict:
        """STEP 1: Preview a trade and return a confirmation token.

        Does NOT execute the trade. The caller must call ``confirm_trade()``
        with the returned ``confirmation_token`` to execute.

        Args:
            symbol: Ticker symbol (e.g. "AAPL").
            quantity: Number of shares.
            order_type: "MARKET" or "LIMIT".
            action: "BUY" or "SELL".
            limit_price: Required if order_type is "LIMIT".

        Returns:
            dict with ``preview`` and ``confirmation_token``.
        """
        if order_type.upper() == "LIMIT" and limit_price is None:
            msg = "limit_price is required for LIMIT orders"
            raise SchwabTradeError(msg)

        order_payload = {
            "orderType": order_type.upper(),
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": action.upper(),
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol.upper(),
                        "assetType": "EQUITY",
                    },
                }
            ],
        }

        if limit_price is not None:
            order_payload["price"] = str(limit_price)

        # Generate preview (estimate)
        preview = {
            "symbol": symbol.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            "action": action.upper(),
            "limit_price": limit_price,
            "estimated_cost": (round(limit_price * quantity, 2) if limit_price else None),
            "status": "PENDING_CONFIRMATION",
        }

        # Generate a secure confirmation token
        confirmation_token = self._generate_confirmation_token(preview)

        # Store the pending order with TTL and user identity binding
        self._pending_confirmations[confirmation_token] = (
            {**preview, "_order_payload": order_payload},
            time.time() + _CONFIRMATION_TTL_SECONDS,
            self.user_id,
        )

        self._log.info(
            "schwab_trade_preview",
            symbol=symbol.upper(),
            action=action.upper(),
            quantity=quantity,
        )
        await self._audit(
            action="schwab_trade_preview",
            resource_type="trade",
            metadata={
                "symbol": symbol.upper(),
                "action": action.upper(),
                "quantity": quantity,
                "order_type": order_type.upper(),
            },
        )

        return {
            "preview": preview,
            "confirmation_token": confirmation_token,
            "expires_in_seconds": _CONFIRMATION_TTL_SECONDS,
        }

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def confirm_trade(self, confirmation_token: str) -> dict:
        """STEP 2: Execute a previously previewed trade.

        Args:
            confirmation_token: Token from ``place_trade()`` response.

        Returns:
            dict with order_id and execution status.

        Raises:
            SchwabTradeError: If the token is invalid, expired, or execution fails.
        """
        # Clean up expired confirmations
        self._cleanup_expired_confirmations()

        pending = self._pending_confirmations.pop(confirmation_token, None)
        if pending is None:
            msg = "Invalid or expired confirmation token"
            raise SchwabTradeError(msg)

        order_data, expiry, token_user_id = pending
        if token_user_id != self.user_id:
            self._log.warning(
                "schwab_trade_confirm_user_mismatch",
                expected_user=token_user_id,
                actual_user=self.user_id,
            )
            msg = "Invalid or expired confirmation token"
            raise SchwabTradeError(msg)
        if time.time() > expiry:
            msg = "Confirmation token has expired"
            raise SchwabTradeError(msg)

        order_payload = order_data.pop("_order_payload")

        try:
            result = await self._api_request(
                "POST",
                "/accounts/orders",
                json=order_payload,
            )

            order_id = result.get("orderId", str(uuid.uuid4()))

            self._log.info(
                "schwab_trade_executed",
                order_id=order_id,
                symbol=order_data.get("symbol"),
            )
            await self._audit(
                action="schwab_trade_execute",
                resource_type="trade",
                resource_id=order_id,
                metadata={
                    "symbol": order_data.get("symbol"),
                    "action": order_data.get("action"),
                    "quantity": order_data.get("quantity"),
                },
            )

            return {
                "order_id": order_id,
                "status": "EXECUTED",
                "details": order_data,
            }

        except httpx.HTTPStatusError as exc:
            self._log.error(
                "schwab_trade_execution_failed",
                status_code=exc.response.status_code,
            )
            msg = f"Trade execution failed: {exc.response.status_code}"
            raise SchwabTradeError(msg) from exc

    @staticmethod
    def _generate_confirmation_token(preview: dict) -> str:
        """Generate a cryptographically secure confirmation token."""
        nonce = secrets.token_hex(16)
        payload = f"{preview['symbol']}:{preview['quantity']}:{preview['action']}:{nonce}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @classmethod
    def _cleanup_expired_confirmations(cls) -> None:
        """Remove expired confirmation tokens from the in-memory store."""
        now = time.time()
        expired = [
            token
            for token, (_, expiry, _user_id) in cls._pending_confirmations.items()
            if now > expiry
        ]
        for token in expired:
            cls._pending_confirmations.pop(token, None)

    # ------------------------------------------------------------------
    # Abstract implementations
    # ------------------------------------------------------------------

    async def sync(self) -> None:
        """Pull latest portfolio data from Schwab."""
        await self.get_portfolio()
        await self.get_transactions()

    async def health_check(self) -> bool:
        """Verify Schwab credentials are valid."""
        try:
            await self.get_portfolio()
            return True
        except Exception:
            self._log.warning("schwab_health_check_failed")
            return False


def _mask_account(account_number: str) -> str:
    """Mask account number, showing only last 4 digits."""
    if len(account_number) <= 4:
        return "****"
    return "*" * (len(account_number) - 4) + account_number[-4:]

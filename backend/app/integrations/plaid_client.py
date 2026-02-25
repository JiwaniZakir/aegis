"""Plaid integration — banking transactions, balances, and recurring charges."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.models.account import Account
from app.models.transaction import Transaction
from app.security.encryption import encrypt_field

logger = structlog.get_logger()

# Conditional import — plaid-python lives in the optional 'integrations' group.
try:
    from plaid.api import plaid_api
    from plaid.api_client import ApiClient
    from plaid.configuration import Configuration
    from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
    from plaid.model.country_code import CountryCode
    from plaid.model.item_public_token_exchange_request import (
        ItemPublicTokenExchangeRequest,
    )
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.products import Products
    from plaid.model.transactions_sync_request import TransactionsSyncRequest

    PLAID_AVAILABLE = True
except ImportError:
    PLAID_AVAILABLE = False

_PLAID_ENV_MAP = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


class PlaidUnavailableError(RuntimeError):
    """Raised when the plaid-python package is not installed."""


class PlaidClient(BaseIntegration):
    """Integration client for Plaid banking APIs.

    Supports link-token creation, public-token exchange, transaction sync,
    balance retrieval, and recurring-transaction detection.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        if not PLAID_AVAILABLE:
            msg = (
                "plaid-python is not installed. "
                "Install with: uv pip install 'aegis[integrations]'"
            )
            raise PlaidUnavailableError(msg)

        settings = get_settings()
        self._client_id = settings.plaid_client_id
        self._secret = settings.plaid_secret
        self._env = settings.plaid_env
        self._api_client = self._build_api_client()
        self._plaid = plaid_api.PlaidApi(self._api_client)

    def _build_api_client(self) -> ApiClient:
        """Build a configured Plaid API client."""
        host = _PLAID_ENV_MAP.get(self._env, _PLAID_ENV_MAP["sandbox"])
        configuration = Configuration(host=host)
        configuration.api_key["clientId"] = self._client_id
        configuration.api_key["secret"] = self._secret
        return ApiClient(configuration)

    # ------------------------------------------------------------------
    # Link flow
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def create_link_token(self) -> dict:
        """Create a Plaid Link token for the frontend to initialize Plaid Link.

        Returns:
            dict with ``link_token`` and ``expiration``.
        """
        try:
            request = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=self.user_id),
                client_name="Aegis",
                products=[Products("transactions")],
                country_codes=[CountryCode("US")],
                language="en",
            )
            response = self._plaid.link_token_create(request)
            self._log.info("plaid_link_token_created")
            await self._audit(
                action="plaid_link_token_create",
                resource_type="plaid",
            )
            return {
                "link_token": response.link_token,
                "expiration": response.expiration,
            }
        except Exception as exc:
            self._log.error("plaid_link_token_failed", error=str(type(exc).__name__))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def exchange_public_token(self, public_token: str) -> str:
        """Exchange a public token from Plaid Link for a persistent access token.

        The access token is encrypted and stored in the credentials table.

        Returns:
            The Plaid item_id.
        """
        try:
            request = ItemPublicTokenExchangeRequest(public_token=public_token)
            response = self._plaid.item_public_token_exchange(request)

            access_token: str = response.access_token
            item_id: str = response.item_id

            # Store encrypted access token
            await self.store_credential("plaid_access_token", access_token)

            self._log.info("plaid_token_exchanged", item_id=item_id)
            await self._audit(
                action="plaid_token_exchange",
                resource_type="plaid",
                resource_id=item_id,
            )
            return item_id
        except Exception as exc:
            self._log.error("plaid_token_exchange_failed", error=str(type(exc).__name__))
            raise

    # ------------------------------------------------------------------
    # Transaction sync
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def sync_transactions(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Fetch transactions via Plaid Transactions Sync and persist to DB.

        Uses the cursor-based sync endpoint for incremental updates.

        Returns:
            List of dicts with transaction summaries (no PII).
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        settings = get_settings()
        access_token = await self.get_credential("plaid_access_token")

        added: list[dict] = []
        has_more = True
        cursor = ""

        try:
            while has_more:
                request = TransactionsSyncRequest(
                    access_token=access_token,
                    cursor=cursor if cursor else None,
                )
                response = self._plaid.transactions_sync(request)
                cursor = response.next_cursor
                has_more = response.has_more

                for txn in response.added:
                    # Encrypt the memo/name field before storage
                    encrypted_memo = None
                    if txn.name:
                        encrypted_memo = encrypt_field(
                            txn.name,
                            settings.master_key_bytes,
                            context=f"transaction.memo.{self.user_id}",
                        )

                    # Upsert: check if transaction already exists
                    existing = await self.db.execute(
                        select(Transaction).where(
                            Transaction.plaid_transaction_id == txn.transaction_id
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        continue

                    # Find or create the account
                    account = await self._get_or_create_account(txn.account_id)

                    db_txn = Transaction(
                        account_id=account.id,
                        amount=Decimal(str(txn.amount)),
                        transaction_date=txn.date,
                        category=txn.personal_finance_category.primary
                        if txn.personal_finance_category
                        else (txn.category[0] if txn.category else None),
                        merchant=txn.merchant_name,
                        encrypted_memo=encrypted_memo,
                        plaid_transaction_id=txn.transaction_id,
                        is_recurring=False,
                    )
                    self.db.add(db_txn)
                    added.append(
                        {
                            "amount": float(txn.amount),
                            "date": str(txn.date),
                            "category": db_txn.category,
                            "merchant": txn.merchant_name,
                        }
                    )

            await self.db.flush()
            self._log.info("plaid_transactions_synced", count=len(added))
            await self._audit(
                action="plaid_transaction_sync",
                resource_type="transaction",
                metadata={"count": len(added)},
            )
            return added

        except KeyError:
            self._log.warning("plaid_no_access_token")
            raise
        except Exception as exc:
            self._log.error("plaid_transaction_sync_failed", error=str(type(exc).__name__))
            raise

    async def _get_or_create_account(self, plaid_account_id: str) -> Account:
        """Find an existing account by Plaid account ID or create a placeholder."""
        import uuid

        result = await self.db.execute(
            select(Account).where(Account.plaid_account_id == plaid_account_id)
        )
        account = result.scalar_one_or_none()
        if account is not None:
            return account

        account = Account(
            user_id=uuid.UUID(self.user_id),
            institution="Plaid",
            account_type="depository",
            account_name=f"Account {plaid_account_id[:8]}",
            plaid_account_id=plaid_account_id,
        )
        self.db.add(account)
        await self.db.flush()
        return account

    # ------------------------------------------------------------------
    # Balances
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def get_balances(self) -> list[dict]:
        """Fetch current balances across all linked Plaid accounts.

        Returns:
            List of dicts with account_id, name, type, balances.
        """
        try:
            access_token = await self.get_credential("plaid_access_token")
            request = AccountsBalanceGetRequest(access_token=access_token)
            response = self._plaid.accounts_balance_get(request)

            balances = []
            for acct in response.accounts:
                balances.append(
                    {
                        "account_id": acct.account_id,
                        "name": acct.name,
                        "type": acct.type.value if acct.type else None,
                        "current": float(acct.balances.current) if acct.balances.current else 0,
                        "available": (
                            float(acct.balances.available) if acct.balances.available else None
                        ),
                        "currency": acct.balances.iso_currency_code or "USD",
                    }
                )

                # Update stored account balance
                db_result = await self.db.execute(
                    select(Account).where(Account.plaid_account_id == acct.account_id)
                )
                db_account = db_result.scalar_one_or_none()
                if db_account:
                    db_account.balance = Decimal(str(acct.balances.current or 0))

            await self.db.flush()
            self._log.info("plaid_balances_fetched", count=len(balances))
            await self._audit(
                action="plaid_balance_fetch",
                resource_type="account",
                metadata={"account_count": len(balances)},
            )
            return balances

        except KeyError:
            self._log.warning("plaid_no_access_token")
            raise
        except Exception as exc:
            self._log.error("plaid_balance_fetch_failed", error=str(type(exc).__name__))
            raise

    # ------------------------------------------------------------------
    # Recurring detection
    # ------------------------------------------------------------------

    async def get_recurring(self) -> list[dict]:
        """Identify recurring transactions from stored transaction history.

        Analyses transactions in the database to find patterns of recurring
        charges (same merchant, similar amount, regular interval).

        Returns:
            List of dicts with merchant, amount, frequency, last_date.
        """
        import uuid
        from collections import defaultdict

        from sqlalchemy import and_

        try:
            # Get all accounts for this user
            accounts = await self.db.execute(
                select(Account).where(Account.user_id == uuid.UUID(self.user_id))
            )
            account_ids = [a.id for a in accounts.scalars().all()]

            if not account_ids:
                return []

            # Fetch transactions from last 90 days
            cutoff = date.today() - timedelta(days=90)
            txn_result = await self.db.execute(
                select(Transaction).where(
                    and_(
                        Transaction.account_id.in_(account_ids),
                        Transaction.transaction_date >= cutoff,
                    )
                )
            )
            transactions = txn_result.scalars().all()

            # Group by merchant and detect recurring patterns
            merchant_txns: dict[str, list[Transaction]] = defaultdict(list)
            for txn in transactions:
                if txn.merchant:
                    merchant_txns[txn.merchant].append(txn)

            recurring = []
            for merchant, txns in merchant_txns.items():
                if len(txns) < 2:
                    continue

                # Sort by date
                txns.sort(key=lambda t: t.transaction_date)
                amounts = [float(t.amount) for t in txns]
                avg_amount = sum(amounts) / len(amounts)

                # Check if amounts are roughly consistent (within 20%)
                consistent = all(
                    abs(a - avg_amount) / max(abs(avg_amount), 0.01) < 0.2 for a in amounts
                )
                if not consistent:
                    continue

                # Estimate frequency from date intervals
                intervals = []
                for i in range(1, len(txns)):
                    diff = (txns[i].transaction_date - txns[i - 1].transaction_date).days
                    intervals.append(diff)

                avg_interval = sum(intervals) / len(intervals) if intervals else 0
                frequency = _classify_frequency(avg_interval)

                if frequency:
                    recurring.append(
                        {
                            "merchant": merchant,
                            "amount": round(avg_amount, 2),
                            "frequency": frequency,
                            "last_date": str(txns[-1].transaction_date),
                            "occurrences": len(txns),
                        }
                    )
                    # Mark as recurring in DB
                    for txn in txns:
                        txn.is_recurring = True

            await self.db.flush()
            self._log.info("plaid_recurring_detected", count=len(recurring))
            await self._audit(
                action="plaid_recurring_analysis",
                resource_type="transaction",
                metadata={"recurring_count": len(recurring)},
            )
            return recurring

        except Exception as exc:
            self._log.error("plaid_recurring_failed", error=str(type(exc).__name__))
            raise

    # ------------------------------------------------------------------
    # Abstract implementations
    # ------------------------------------------------------------------

    async def sync(self) -> None:
        """Pull latest transactions and balances from Plaid."""
        await self.sync_transactions()
        await self.get_balances()

    async def health_check(self) -> bool:
        """Verify Plaid credentials are valid by attempting a balance fetch."""
        try:
            await self.get_balances()
            return True
        except Exception:
            self._log.warning("plaid_health_check_failed")
            return False


def _classify_frequency(avg_interval_days: float) -> str | None:
    """Classify a recurring frequency from average interval in days."""
    if 5 <= avg_interval_days <= 10:
        return "weekly"
    if 12 <= avg_interval_days <= 18:
        return "bi-weekly"
    if 25 <= avg_interval_days <= 35:
        return "monthly"
    if 55 <= avg_interval_days <= 70:
        return "bi-monthly"
    if 80 <= avg_interval_days <= 100:
        return "quarterly"
    if 340 <= avg_interval_days <= 380:
        return "annual"
    return None

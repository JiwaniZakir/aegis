"""Celery task — periodic finance data synchronization."""

from __future__ import annotations

import asyncio

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="app.tasks.finance_sync.sync_finances",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_finances(self: object) -> dict:
    """Synchronize financial data from all linked accounts.

    Runs every 6 hours via Celery Beat. Pulls latest transactions and
    balances from Plaid, then detects recurring charges.
    """
    logger.info("finance_sync_started")

    try:
        result = asyncio.run(_sync_all_finances())
        logger.info("finance_sync_completed", result=result)
        return result
    except Exception as exc:
        logger.error("finance_sync_failed", error=str(type(exc).__name__))
        raise self.retry(exc=exc) from exc  # type: ignore[attr-defined]


async def _sync_all_finances() -> dict:
    """Async implementation of the finance sync task.

    Fetches all users with linked Plaid accounts and syncs each one.
    """
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.credential import Credential

    results = {"users_synced": 0, "errors": []}

    async with async_session_factory() as db:
        # Find all users with plaid credentials
        cred_result = await db.execute(
            select(Credential.user_id).where(Credential.service_name == "plaid_access_token")
        )
        user_ids = [str(row[0]) for row in cred_result.fetchall()]

        for user_id in user_ids:
            try:
                await _sync_user_finances(db, user_id)
                results["users_synced"] += 1
            except Exception as exc:
                logger.error(
                    "finance_sync_user_failed",
                    user_id=user_id,
                    error=str(type(exc).__name__),
                )
                results["errors"].append({"user_id": user_id, "error": str(type(exc).__name__)})

        await db.commit()

    return results


async def _sync_user_finances(db: object, user_id: str) -> None:
    """Sync finance data for a single user."""
    from sqlalchemy.ext.asyncio import AsyncSession

    session: AsyncSession = db  # type: ignore[assignment]

    try:
        from app.integrations.plaid_client import PLAID_AVAILABLE, PlaidClient

        if not PLAID_AVAILABLE:
            logger.warning("plaid_not_installed_skipping_sync")
            return

        client = PlaidClient(user_id, session)
        await client.sync_transactions()
        await client.get_balances()
        await client.get_recurring()

        logger.info("finance_sync_user_complete", user_id=user_id)

    except ImportError:
        logger.warning("plaid_import_failed_skipping_sync")
    except KeyError:
        logger.warning("plaid_no_credentials", user_id=user_id)
    except Exception as exc:
        logger.error(
            "finance_sync_user_error",
            user_id=user_id,
            error=str(type(exc).__name__),
        )
        raise

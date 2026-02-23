"""BaseIntegration ABC — all external integrations inherit from this."""

from __future__ import annotations

from abc import ABC, abstractmethod

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.security.audit import audit_log
from app.security.encryption import decrypt_credential, encrypt_credential

logger = structlog.get_logger()


class BaseIntegration(ABC):
    """Base class for all external API integrations.

    Enforces audit logging, secure credential access, and structured logging
    for every integration client. Subclasses MUST implement ``sync`` and
    ``health_check``.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        self.user_id = user_id
        self.db = db
        self._log = logger.bind(
            integration=self.__class__.__name__,
            user_id=user_id,
        )

    async def get_credential(self, key: str) -> str:
        """Fetch and decrypt a stored credential. Never cache in plaintext."""
        settings = get_settings()
        self._log.debug("credential_fetch", service=key)
        return await decrypt_credential(
            self.db,
            self.user_id,
            key,
            settings.master_key_bytes,
        )

    async def store_credential(self, key: str, value: str) -> None:
        """Encrypt and store a credential in the database."""
        settings = get_settings()
        self._log.debug("credential_store", service=key)
        await encrypt_credential(
            self.db,
            self.user_id,
            key,
            value,
            settings.master_key_bytes,
        )

    async def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        detail: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Write an audit log entry for this integration action."""
        import uuid as _uuid

        await audit_log(
            self.db,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=_uuid.UUID(self.user_id),
            detail=detail,
            metadata=metadata,
        )

    @abstractmethod
    async def sync(self) -> None:
        """Pull latest data from external service."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify connection is alive and credentials are valid."""
        ...

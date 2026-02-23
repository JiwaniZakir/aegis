"""AES-256-GCM field-level encryption for PII and sensitive data."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_field(plaintext: str, master_key: bytes, context: str | None = None) -> str:
    """Encrypt a string with AES-256-GCM.

    Returns base64-encoded nonce (12 bytes) + ciphertext + tag (16 bytes).

    Args:
        plaintext: The string to encrypt.
        master_key: 32-byte AES-256 key.
        context: Optional Associated Authenticated Data (AAD) string that binds
            the ciphertext to a specific usage context (e.g. field name + record ID).
            Prevents ciphertext transplant attacks between fields. The same context
            must be provided during decryption.
    """
    if len(master_key) != 32:  # noqa: PLR2004
        msg = "Master key must be exactly 32 bytes for AES-256"
        raise ValueError(msg)

    nonce = os.urandom(12)
    aesgcm = AESGCM(master_key)
    aad = context.encode("utf-8") if context is not None else None
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(encrypted: str, master_key: bytes, context: str | None = None) -> str:
    """Decrypt an AES-256-GCM encrypted field.

    Expects base64-encoded nonce (12 bytes) + ciphertext + tag.

    Args:
        encrypted: Base64-encoded ciphertext produced by ``encrypt_field``.
        master_key: 32-byte AES-256 key (must match the key used for encryption).
        context: Optional Associated Authenticated Data (AAD) string. Must match
            the context supplied during encryption, otherwise decryption will fail.
    """
    if len(master_key) != 32:  # noqa: PLR2004
        msg = "Master key must be exactly 32 bytes for AES-256"
        raise ValueError(msg)

    raw = base64.b64decode(encrypted)
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(master_key)
    aad = context.encode("utf-8") if context is not None else None
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
    return plaintext.decode("utf-8")


async def encrypt_credential(
    db_session: object,
    user_id: str,
    key: str,
    value: str,
    master_key: bytes,
) -> None:
    """Encrypt and store a credential in the database."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.credential import Credential

    session: AsyncSession = db_session  # type: ignore[assignment]
    context = f"clawdbot:credentials:user:{user_id}:service:{key}"
    encrypted = encrypt_field(value, master_key, context=context)

    stmt = select(Credential).where(
        Credential.user_id == user_id,
        Credential.service_name == key,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_value = encrypted
    else:
        cred = Credential(
            user_id=user_id,
            service_name=key,
            encrypted_value=encrypted,
        )
        session.add(cred)


async def decrypt_credential(
    db_session: object,
    user_id: str,
    key: str,
    master_key: bytes,
) -> str:
    """Retrieve and decrypt a stored credential."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.credential import Credential

    session: AsyncSession = db_session  # type: ignore[assignment]

    stmt = select(Credential).where(
        Credential.user_id == user_id,
        Credential.service_name == key,
    )
    result = await session.execute(stmt)
    cred = result.scalar_one_or_none()

    if cred is None:
        msg = f"No credential found for user={user_id}, service={key}"
        raise KeyError(msg)

    context = f"clawdbot:credentials:user:{user_id}:service:{key}"
    return decrypt_field(cred.encrypted_value, master_key, context=context)

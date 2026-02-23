"""Tests for AES-256-GCM field encryption."""

from __future__ import annotations

import pytest

from app.security.encryption import decrypt_field, encrypt_field


def test_encrypt_decrypt_roundtrip(master_key: bytes):
    """Encrypt then decrypt returns original plaintext."""
    plaintext = "sensitive financial data: account 1234-5678"
    encrypted = encrypt_field(plaintext, master_key)
    decrypted = decrypt_field(encrypted, master_key)
    assert decrypted == plaintext


def test_encrypted_differs_from_plaintext(master_key: bytes):
    """Encrypted output must not contain the original plaintext."""
    plaintext = "my secret api key"
    encrypted = encrypt_field(plaintext, master_key)
    assert plaintext not in encrypted


def test_different_encryptions_produce_different_ciphertext(master_key: bytes):
    """Each encryption uses a unique nonce, so ciphertexts differ."""
    plaintext = "same input"
    enc1 = encrypt_field(plaintext, master_key)
    enc2 = encrypt_field(plaintext, master_key)
    assert enc1 != enc2


def test_wrong_key_fails(master_key: bytes):
    """Decryption with wrong key raises an error."""
    plaintext = "secret"
    encrypted = encrypt_field(plaintext, master_key)
    wrong_key = b"\x00" * 32
    with pytest.raises(Exception):  # noqa: B017, S110
        decrypt_field(encrypted, wrong_key)


def test_invalid_key_length_rejected():
    """Keys that aren't 32 bytes are rejected."""
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt_field("test", b"short_key")


def test_empty_string_roundtrip(master_key: bytes):
    """Empty strings can be encrypted and decrypted."""
    encrypted = encrypt_field("", master_key)
    assert decrypt_field(encrypted, master_key) == ""


def test_unicode_roundtrip(master_key: bytes):
    """Unicode content survives encryption round-trip."""
    plaintext = "Name: Zakir Jiwani, SSN: 123-45-6789, Amount: $1,234.56"
    encrypted = encrypt_field(plaintext, master_key)
    assert decrypt_field(encrypted, master_key) == plaintext


def test_aad_context_roundtrip(master_key: bytes):
    """Encrypt and decrypt with the same AAD context succeeds."""
    plaintext = "account-number-9876"
    context = "credentials.plaid_token.user-42"
    encrypted = encrypt_field(plaintext, master_key, context=context)
    decrypted = decrypt_field(encrypted, master_key, context=context)
    assert decrypted == plaintext


def test_aad_context_mismatch(master_key: bytes):
    """Decryption with a different AAD context must fail (ciphertext transplant)."""
    plaintext = "account-number-9876"
    context_a = "credentials.plaid_token.user-42"
    context_b = "credentials.schwab_token.user-42"
    encrypted = encrypt_field(plaintext, master_key, context=context_a)
    with pytest.raises(Exception):  # noqa: B017
        decrypt_field(encrypted, master_key, context=context_b)

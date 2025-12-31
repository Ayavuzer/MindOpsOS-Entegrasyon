"""Encryption utilities for storing sensitive credentials."""

import os
from cryptography.fernet import Fernet


def get_encryption_key() -> bytes:
    """Get encryption key from environment."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # Generate a key for development (should be set in production)
        key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = key
        print(f"⚠️  Generated new encryption key (set ENCRYPTION_KEY in production)")
    return key.encode() if isinstance(key, str) else key


_fernet = None


def get_fernet() -> Fernet:
    """Get Fernet instance."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


def encrypt_value(plain_text: str) -> str:
    """Encrypt a string value and return as string for database storage."""
    if not plain_text:
        return None
    return get_fernet().encrypt(plain_text.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt an encrypted value stored as string."""
    if not encrypted:
        return None
    try:
        # Handle both string and bytes input
        if isinstance(encrypted, str):
            encrypted = encrypted.encode()
        return get_fernet().decrypt(encrypted).decode()
    except Exception:
        return None

"""
Field-level encryption utilities for Asfalis.

Architecture
────────────
• EncryptedString  — SQLAlchemy TypeDecorator backed by Text.
                     Encrypts on write; decrypts on read. Transparent to routes/services.
• EncryptedFloat   — Same idea for latitude/longitude floats, serialised as decimal strings.
• EncryptedJSON    — For JSON columns (e.g. contacted_numbers) serialised via json.dumps.
• compute_hmac     — Deterministic HMAC-SHA256 fingerprint used as a "search-safe" index
                     next to each encrypted phone/email/IMEI/MAC column so SQL equality
                     lookups still work without storing plaintext.

Keys (loaded from environment via app.config)
─────────────────────────────────────────────
  FIELD_ENCRYPTION_KEY  Fernet URL-safe base64 32-byte key.
                        Generate:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  FIELD_HMAC_KEY        Arbitrary secret string used as the HMAC key.

Both values are lazy-loaded on first use so the module can be imported before the
environment is fully configured (import-time side effects avoided).
"""

import json
import hmac as _hmac
import hashlib
import logging
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

# ── Key management ─────────────────────────────────────────────────────────────

_fernet: Optional[Fernet] = None
_hmac_key: Optional[bytes] = None


def _get_fernet() -> Fernet:
    """Lazily initialise the Fernet cipher from the FIELD_ENCRYPTION_KEY env var."""
    global _fernet
    if _fernet is None:
        from app.config import settings
        key = settings.FIELD_ENCRYPTION_KEY
        if not key:
            raise RuntimeError(
                "FIELD_ENCRYPTION_KEY is not set. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def _get_hmac_key() -> bytes:
    """Lazily load FIELD_HMAC_KEY as bytes."""
    global _hmac_key
    if _hmac_key is None:
        from app.config import settings
        key = settings.FIELD_HMAC_KEY
        if not key:
            raise RuntimeError(
                "FIELD_HMAC_KEY is not set. "
                "Set it to any sufficiently random secret string in your .env file."
            )
        _hmac_key = key.encode() if isinstance(key, str) else key
    return _hmac_key


# ── Public helpers ─────────────────────────────────────────────────────────────

def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns a Fernet token (URL-safe base64 string)."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token. Raises InvalidToken on tampering/wrong key."""
    return _get_fernet().decrypt(token.encode()).decode()


def compute_hmac(value: str) -> str:
    """
    Return a hex-encoded HMAC-SHA256 of *value* using FIELD_HMAC_KEY.

    Used to build deterministic search-index columns so we can do equality
    lookups on encrypted fields without storing plaintext.
    The value is lowercased + stripped before hashing for consistency.
    """
    normalised = value.strip().lower()
    return _hmac.new(_get_hmac_key(), normalised.encode(), hashlib.sha256).hexdigest()


def is_encrypted(value: str) -> bool:
    """
    Heuristic check: Fernet tokens always start with 'gAAAAA'.
    Used by the migration script to skip already-encrypted rows.
    """
    return isinstance(value, str) and value.startswith('gAAAAA')


# ── SQLAlchemy TypeDecorators ─────────────────────────────────────────────────

class EncryptedString(TypeDecorator):
    """
    Stores an arbitrary string as a Fernet-encrypted blob in a Text column.

    Usage in a model:
        name = Column(EncryptedString(), nullable=False)
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """Called before INSERT / UPDATE — encrypt the plaintext value."""
        if value is None:
            return None
        return encrypt(str(value))

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """Called after SELECT — decrypt the ciphertext value."""
        if value is None:
            return None
        try:
            return decrypt(value)
        except (InvalidToken, Exception) as exc:
            # Log but don't crash — returns None so callers can handle gracefully
            logger.error("EncryptedString: decryption failed — %s", exc)
            return None


class EncryptedFloat(TypeDecorator):
    """
    Stores a float as a Fernet-encrypted decimal string in a Text column.

    Used for latitude / longitude so their exact values are never stored in plaintext.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[float], dialect) -> Optional[str]:
        if value is None:
            return None
        # Preserve full IEEE 754 precision
        return encrypt(repr(float(value)))

    def process_result_value(self, value: Optional[str], dialect) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(decrypt(value))
        except (InvalidToken, ValueError, Exception) as exc:
            logger.error("EncryptedFloat: decryption failed — %s", exc)
            return None


class EncryptedJSON(TypeDecorator):
    """
    Stores a Python dict/list as a Fernet-encrypted JSON blob in a Text column.

    Drop-in replacement for SQLAlchemy's JSON column type on sensitive fields
    (e.g. contacted_numbers in SOSAlert).
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[Any], dialect) -> Optional[str]:
        if value is None:
            return None
        return encrypt(json.dumps(value, ensure_ascii=False))

    def process_result_value(self, value: Optional[str], dialect) -> Optional[Any]:
        if value is None:
            return None
        try:
            return json.loads(decrypt(value))
        except (InvalidToken, json.JSONDecodeError, Exception) as exc:
            logger.error("EncryptedJSON: decryption failed — %s", exc)
            return None

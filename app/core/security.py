import hashlib
import os
import base64
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# Use the bcrypt library directly. passlib 1.7.4 is unmaintained and crashes
# against bcrypt >= 4.1 (its internal self-test hashes a >72-byte string).
_BCRYPT_ROUNDS = 12
_BCRYPT_MAX_BYTES = 72  # bcrypt only considers the first 72 bytes of the secret


def hash_password(password: str) -> str:
    digest = bcrypt.hashpw(
        password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    )
    return digest.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        plain.encode("utf-8")[:_BCRYPT_MAX_BYTES], hashed.encode("utf-8")
    )


def generate_api_key() -> tuple[str, str]:
    """Return (raw_key, sha256_hash). Show raw_key to user once, store only hash."""
    raw = base64.urlsafe_b64encode(os.urandom(32)).decode()
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, key_hash


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Raises JWTError on invalid/expired tokens."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

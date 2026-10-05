"""Password hashing (argon2) and JWT access tokens / opaque refresh tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.errors import unauthorized

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(password, password_hash)
    except Exception:  # malformed hash - treat as mismatch
        return False


def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    expires_in = settings.jwt_access_expiration_minutes * 60
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized("Access token expired.", "TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise unauthorized("Invalid access token.", "TOKEN_INVALID") from exc
    if payload.get("type") != "access":
        raise unauthorized("Invalid token type.", "TOKEN_INVALID")
    return payload


def new_refresh_token() -> str:
    """Opaque, high-entropy refresh token. Only its SHA-256 hash is stored."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expiration_days)

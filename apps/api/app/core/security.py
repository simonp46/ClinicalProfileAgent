"""Security helpers for auth and encryption."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityError(Exception):
    """Base security error."""


class CSRFError(SecurityError):
    """Raised when CSRF validation fails."""


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _build_token(
    subject: str,
    expires_delta: timedelta,
    token_type: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return _build_token(
        subject=subject,
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
        token_type="access",
    )


def create_refresh_token(subject: str) -> str:
    return _build_token(
        subject=subject,
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
        token_type="refresh",
    )


def create_provider_oauth_state(subject: str, provider: str) -> str:
    return _build_token(
        subject=subject,
        expires_delta=timedelta(minutes=15),
        token_type=f"{provider}_oauth_state",
    )


def create_google_oauth_state(subject: str) -> str:
    return create_provider_oauth_state(subject, "google")


def create_microsoft_oauth_state(subject: str) -> str:
    return create_provider_oauth_state(subject, "microsoft")


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:  # pragma: no cover - jose emits detailed subclasses
        raise SecurityError("Invalid token") from exc

    if payload.get("type") != expected_type:
        raise SecurityError("Token type mismatch")
    return payload


def build_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def validate_csrf(header_token: str | None, cookie_token: str | None) -> None:
    if not settings.csrf_enabled:
        return
    if not header_token or not cookie_token or header_token != cookie_token:
        raise CSRFError("Invalid CSRF token")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _resolve_fernet() -> Fernet | None:
    key = settings.encryption_key
    if not key:
        return None
    try:
        if len(key) == 44:
            return Fernet(key.encode("utf-8"))
        normalized = base64.urlsafe_b64encode(key.encode("utf-8")[:32].ljust(32, b"0"))
        return Fernet(normalized)
    except Exception:
        return None


def encrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    fernet = _resolve_fernet()
    if fernet is None:
        return value
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    fernet = _resolve_fernet()
    if fernet is None:
        return value
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return value

"""Custom SQLAlchemy column types."""

from __future__ import annotations

from typing import Any

from sqlalchemy.types import String, TypeDecorator

from app.core.security import decrypt_value, encrypt_value


class EncryptedString(TypeDecorator[str]):
    """Encrypt/decrypt string values transparently."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        _ = dialect
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        _ = dialect
        return decrypt_value(value)
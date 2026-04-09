"""Authentication application service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    build_csrf_token,
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domain.models import AuthRefreshToken, Therapist


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register_therapist(
        self,
        *,
        full_name: str,
        email: str,
        password: str,
        google_account_email: str | None = None,
    ) -> Therapist:
        existing = self.db.scalar(select(Therapist).where(Therapist.email == email))
        if existing is not None:
            raise ValueError("Email already registered")

        therapist = Therapist(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            google_account_email=google_account_email,
            contact_email=email,
        )
        self.db.add(therapist)
        self.db.flush()
        return therapist

    def authenticate(self, email: str, password: str) -> Therapist | None:
        therapist = self.db.scalar(select(Therapist).where(Therapist.email == email))
        if therapist is None:
            return None
        if not verify_password(password, therapist.password_hash):
            return None
        return therapist

    def build_login_tokens(self, therapist: Therapist) -> tuple[str, str, str]:
        access_token = create_access_token(therapist.id)
        refresh_token = create_refresh_token(therapist.id)
        csrf_token = build_csrf_token()

        refresh = AuthRefreshToken(
            therapist_id=therapist.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
            revoked=False,
        )
        self.db.add(refresh)
        self.db.flush()
        return access_token, refresh_token, csrf_token

    def validate_refresh(self, refresh_token: str) -> Therapist | None:
        from app.core.security import decode_token

        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except Exception:
            return None

        token_hash = hash_token(refresh_token)
        refresh_record = self.db.scalar(
            select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
        )
        if refresh_record is None or refresh_record.revoked:
            return None
        if refresh_record.expires_at < datetime.now(UTC):
            return None

        therapist_id = str(payload["sub"])
        therapist = self.db.scalar(select(Therapist).where(Therapist.id == therapist_id))
        return therapist

    def revoke_refresh(self, refresh_token: str) -> None:
        token_hash = hash_token(refresh_token)
        refresh_record = self.db.scalar(
            select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
        )
        if refresh_record:
            refresh_record.revoked = True
            self.db.add(refresh_record)

    def revoke_all_for_therapist(self, therapist_id: str) -> None:
        records = self.db.scalars(
            select(AuthRefreshToken).where(AuthRefreshToken.therapist_id == therapist_id)
        ).all()
        for record in records:
            record.revoked = True
            self.db.add(record)

    def update_therapist_profile(self, therapist: Therapist, updates: dict[str, Any]) -> Therapist:
        for field, value in updates.items():
            if value is not None:
                setattr(therapist, field, value)
            else:
                setattr(therapist, field, None)

        self.db.add(therapist)
        return therapist

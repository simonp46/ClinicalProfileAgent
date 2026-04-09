"""Authentication application service."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditService
from app.core.config import settings
from app.core.security import (
    build_csrf_token,
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domain.enums import AuditActorType
from app.domain.models import AuthRefreshToken, PasswordResetCode, Therapist
from app.infrastructure.adapters.email_delivery_adapter import EmailDeliveryAdapter


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.email_adapter = EmailDeliveryAdapter()
        self.audit = AuditService(db)

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

    def request_password_reset(self, email: str) -> None:
        therapist = self.db.scalar(select(Therapist).where(Therapist.email == email))
        if therapist is None:
            return

        self.db.execute(
            delete(PasswordResetCode).where(
                PasswordResetCode.therapist_id == therapist.id,
                PasswordResetCode.consumed_at.is_(None),
            )
        )

        code = f"{secrets.randbelow(1_000_000):06d}"
        reset_code = PasswordResetCode(
            therapist_id=therapist.id,
            email=therapist.email,
            code_hash=hash_token(code),
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.password_reset_code_expire_minutes),
        )
        self.db.add(reset_code)
        self.db.flush()

        delivery = self.email_adapter.send_password_reset_code(
            recipient=therapist.email,
            full_name=therapist.full_name,
            code=code,
        )

        self.audit.log(
            actor_type=AuditActorType.system,
            actor_id=None,
            entity_type="therapist",
            entity_id=therapist.id,
            action="therapist.password_reset_requested",
            metadata={
                "email": therapist.email,
                "delivered": delivery.delivered,
                "artifact_path": delivery.artifact_path,
            },
        )

    def reset_password(self, *, email: str, code: str, new_password: str) -> None:
        therapist = self.db.scalar(select(Therapist).where(Therapist.email == email))
        if therapist is None:
            raise ValueError("Codigo invalido o expirado")

        if len(new_password) < 8:
            raise ValueError("La contrasena debe tener al menos 8 caracteres")

        now = datetime.now(UTC)
        code_hash = hash_token(code.strip())
        reset_code = self.db.scalar(
            select(PasswordResetCode)
            .where(
                PasswordResetCode.therapist_id == therapist.id,
                PasswordResetCode.email == therapist.email,
                PasswordResetCode.code_hash == code_hash,
                PasswordResetCode.consumed_at.is_(None),
                PasswordResetCode.expires_at >= now,
            )
            .order_by(PasswordResetCode.created_at.desc())
        )
        if reset_code is None:
            raise ValueError("Codigo invalido o expirado")

        therapist.password_hash = hash_password(new_password)
        reset_code.consumed_at = now
        self.db.add(therapist)
        self.db.add(reset_code)
        self.revoke_all_for_therapist(therapist.id)
        self.db.execute(
            delete(PasswordResetCode).where(
                PasswordResetCode.therapist_id == therapist.id,
                PasswordResetCode.id != reset_code.id,
            )
        )
        self.audit.log(
            actor_type=AuditActorType.system,
            actor_id=None,
            entity_type="therapist",
            entity_id=therapist.id,
            action="therapist.password_reset_completed",
            metadata={"email": therapist.email},
        )

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

"""Microsoft OAuth application service for therapist-owned Teams/Graph access."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import SecurityError, create_microsoft_oauth_state, decode_token
from app.domain.models import Therapist
from app.domain.schemas import GoogleOAuthCallbackResult

MICROSOFT_OAUTH_SCOPES = [
    "offline_access",
    "openid",
    "profile",
    "email",
    "User.Read",
    "Calendars.Read",
    "OnlineMeetings.Read",
    "OnlineMeetingTranscript.Read.All",
]


class MicrosoftOAuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_authorization_url(self, therapist: Therapist) -> str:
        params = {
            "client_id": self._client_id,
            "response_type": "code",
            "redirect_uri": self._redirect_uri,
            "response_mode": "query",
            "scope": " ".join(MICROSOFT_OAUTH_SCOPES),
            "state": create_microsoft_oauth_state(therapist.id),
            "prompt": "select_account",
        }
        return (
            f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/authorize?"
            f"{urlencode(params)}"
        )

    def complete_authorization(
        self,
        *,
        code: str,
        state: str,
    ) -> tuple[Therapist, GoogleOAuthCallbackResult]:
        therapist = self._resolve_therapist_from_state(state)

        response = httpx.post(
            f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._redirect_uri,
                "scope": " ".join(MICROSOFT_OAUTH_SCOPES),
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo completar la autorizacion con Microsoft.",
            )

        payload = response.json()
        access_token = str(payload.get("access_token") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip() or None
        scope_text = str(payload.get("scope") or "").strip()
        expires_in = int(payload.get("expires_in") or 0)
        connected_email = self._resolve_connected_email(access_token)
        scopes = sorted(scope_text.split()) if scope_text else list(MICROSOFT_OAUTH_SCOPES)

        therapist.microsoft_oauth_subject = connected_email or therapist.microsoft_account_email
        therapist.microsoft_oauth_access_token = access_token or None
        therapist.microsoft_oauth_refresh_token = (
            refresh_token or therapist.microsoft_oauth_refresh_token
        )
        therapist.microsoft_oauth_scopes = " ".join(scopes)
        therapist.microsoft_oauth_token_expiry = (
            datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in > 0 else None
        )
        therapist.microsoft_oauth_connected_at = datetime.now(UTC)
        if connected_email and not therapist.microsoft_account_email:
            therapist.microsoft_account_email = connected_email

        self.db.add(therapist)
        return therapist, GoogleOAuthCallbackResult(
            connected_email=connected_email,
            granted_scopes=scopes,
        )

    def disconnect(self, therapist: Therapist) -> Therapist:
        therapist.microsoft_oauth_subject = None
        therapist.microsoft_oauth_access_token = None
        therapist.microsoft_oauth_refresh_token = None
        therapist.microsoft_oauth_scopes = None
        therapist.microsoft_oauth_token_expiry = None
        therapist.microsoft_oauth_connected_at = None
        self.db.add(therapist)
        return therapist

    def _resolve_connected_email(self, access_token: str) -> str | None:
        if not access_token:
            return None
        response = httpx.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        if response.status_code >= 400:
            return None
        payload = response.json()
        if not isinstance(payload, dict):
            return None
        email = payload.get("mail") or payload.get("userPrincipalName")
        return str(email).strip() if email else None

    def _resolve_therapist_from_state(self, state: str) -> Therapist:
        try:
            payload = decode_token(state, expected_type="microsoft_oauth_state")
        except SecurityError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Microsoft OAuth state invalido",
            ) from exc

        therapist_id = str(payload.get("sub") or "").strip()
        therapist = self.db.scalar(select(Therapist).where(Therapist.id == therapist_id))
        if therapist is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado para Microsoft OAuth",
            )
        return therapist

    @property
    def _client_id(self) -> str:
        client_id = (settings.microsoft_oauth_client_id or "").strip()
        if not client_id:
            raise self._configuration_error()
        return client_id

    @property
    def _client_secret(self) -> str:
        client_secret = (settings.microsoft_oauth_client_secret or "").strip()
        if not client_secret:
            raise self._configuration_error()
        return client_secret

    @property
    def _redirect_uri(self) -> str:
        redirect_uri = (settings.microsoft_oauth_redirect_uri or "").strip()
        if not redirect_uri:
            raise self._configuration_error()
        return redirect_uri

    @property
    def _tenant_id(self) -> str:
        return (settings.microsoft_oauth_tenant_id or "common").strip() or "common"

    def _configuration_error(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Microsoft OAuth no esta configurado. Define MICROSOFT_OAUTH_CLIENT_ID, "
                "MICROSOFT_OAUTH_CLIENT_SECRET y MICROSOFT_OAUTH_REDIRECT_URI."
            ),
        )

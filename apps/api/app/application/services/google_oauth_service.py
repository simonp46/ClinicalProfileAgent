"""Google OAuth application service for therapist-owned Workspace access."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import SecurityError, create_google_oauth_state, decode_token
from app.domain.models import Therapist
from app.domain.schemas import GoogleOAuthCallbackResult

GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class GoogleOAuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_authorization_url(self, therapist: Therapist) -> str:
        flow = self._build_flow(state=create_google_oauth_state(therapist.id))
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return authorization_url

    def complete_authorization(self, *, code: str, state: str) -> tuple[Therapist, GoogleOAuthCallbackResult]:
        therapist = self._resolve_therapist_from_state(state)
        flow = self._build_flow(state=state)
        flow.fetch_token(code=code)
        credentials = flow.credentials

        connected_email = self._resolve_connected_email(credentials)
        scopes = sorted(list(credentials.scopes or GOOGLE_OAUTH_SCOPES))

        therapist.google_oauth_subject = connected_email or therapist.google_account_email
        therapist.google_oauth_access_token = credentials.token
        therapist.google_oauth_refresh_token = credentials.refresh_token or therapist.google_oauth_refresh_token
        therapist.google_oauth_scopes = " ".join(scopes)
        therapist.google_oauth_token_expiry = credentials.expiry.astimezone(UTC) if credentials.expiry else None
        therapist.google_oauth_connected_at = datetime.now(UTC)

        if connected_email and not therapist.google_account_email:
            therapist.google_account_email = connected_email

        self.db.add(therapist)
        return therapist, GoogleOAuthCallbackResult(connected_email=connected_email, granted_scopes=scopes)

    def disconnect(self, therapist: Therapist) -> Therapist:
        therapist.google_oauth_subject = None
        therapist.google_oauth_access_token = None
        therapist.google_oauth_refresh_token = None
        therapist.google_oauth_scopes = None
        therapist.google_oauth_token_expiry = None
        therapist.google_oauth_connected_at = None
        self.db.add(therapist)
        return therapist

    def _resolve_therapist_from_state(self, state: str) -> Therapist:
        try:
            payload = decode_token(state, expected_type="google_oauth_state")
        except SecurityError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google OAuth state invalido") from exc

        therapist_id = str(payload.get("sub") or "").strip()
        therapist = self.db.scalar(select(Therapist).where(Therapist.id == therapist_id))
        if therapist is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado para Google OAuth")
        return therapist

    def _resolve_connected_email(self, credentials: Any) -> str | None:
        from googleapiclient.discovery import build

        try:
            oauth_service = build("oauth2", "v2", credentials=credentials, cache_discovery=False)
            profile = oauth_service.userinfo().get().execute()
        except Exception:
            return None

        email = profile.get("email") if isinstance(profile, dict) else None
        return str(email).strip() if email else None

    def _build_flow(self, *, state: str) -> Flow:
        client_id = (settings.google_oauth_client_id or "").strip()
        client_secret = (settings.google_oauth_client_secret or "").strip()
        redirect_uri = (settings.google_oauth_redirect_uri or "").strip()

        if not client_id or not client_secret or not redirect_uri:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Google OAuth no esta configurado. Define GOOGLE_OAUTH_CLIENT_ID, "
                    "GOOGLE_OAUTH_CLIENT_SECRET y GOOGLE_OAUTH_REDIRECT_URI."
                ),
            )

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GOOGLE_OAUTH_SCOPES,
            state=state,
        )
        flow.redirect_uri = redirect_uri
        return flow

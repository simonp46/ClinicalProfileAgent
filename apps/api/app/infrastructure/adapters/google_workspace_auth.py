"""Helpers for therapist-owned Google OAuth and delegated Workspace credentials."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from app.core.config import settings

if TYPE_CHECKING:
    from app.domain.models import Therapist


class GoogleWorkspaceAuthError(ValueError):
    """Raised when the real Google Workspace integration can't resolve credentials."""


def resolve_google_subject(*, impersonated_user: str | None = None) -> str:
    """Resolve the effective Google Workspace user for delegated calls."""

    subject = (impersonated_user or settings.google_impersonated_user or "").strip()
    if not subject:
        raise GoogleWorkspaceAuthError(
            "No Google Workspace account is configured. Set the therapist's Google Workspace email "
            "in the profile, connect Google OAuth, or provide GOOGLE_IMPERSONATED_USER."
        )
    return subject


def has_google_oauth_connection(therapist: Therapist | None) -> bool:
    return bool(therapist and therapist.google_oauth_refresh_token)


def build_google_credentials(
    *,
    scopes: Sequence[str],
    therapist: Therapist | None = None,
    impersonated_user: str | None = None,
):
    """Build OAuth credentials for the therapist when available, else service-account delegation."""

    if has_google_oauth_connection(therapist):
        return build_oauth_credentials(scopes=scopes, therapist=therapist)
    return build_delegated_credentials(scopes=scopes, impersonated_user=impersonated_user)


def build_oauth_credentials(*, scopes: Sequence[str], therapist: Therapist):
    """Create Google OAuth user credentials from stored therapist refresh token."""

    from google.oauth2.credentials import Credentials

    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise GoogleWorkspaceAuthError(
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are required for therapist Google OAuth."
        )
    if not therapist.google_oauth_refresh_token:
        raise GoogleWorkspaceAuthError("The therapist has not connected a Google account yet.")

    return Credentials(
        token=therapist.google_oauth_access_token,
        refresh_token=therapist.google_oauth_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=list(scopes),
    )


def build_delegated_credentials(
    *,
    scopes: Sequence[str],
    impersonated_user: str | None = None,
):
    """Create service-account credentials impersonating the configured Workspace user."""

    from google.oauth2 import service_account

    if not settings.google_service_account_file:
        raise GoogleWorkspaceAuthError("GOOGLE_SERVICE_ACCOUNT_FILE is required for real Google integration.")

    subject = resolve_google_subject(impersonated_user=impersonated_user)
    credentials = service_account.Credentials.from_service_account_file(
        settings.google_service_account_file,
        scopes=list(scopes),
    )
    return credentials.with_subject(subject)

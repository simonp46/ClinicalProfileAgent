from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.google_oauth_service import GoogleOAuthService
from app.domain.models import Therapist
from app.domain.schemas import GoogleOAuthCallbackResult


def _register(client) -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "OAuth Demo",
            "email": "oauth@clinic.com",
            "password": "supersecure123",
            "google_account_email": "oauth@workspace.com",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"], "oauth@clinic.com"


def test_google_connect_route_returns_authorization_url(client, monkeypatch) -> None:
    token, _ = _register(client)

    def _fake_build_authorization_url(self, therapist):
        assert therapist.google_account_email == "oauth@workspace.com"
        return "https://accounts.google.com/mock-consent"

    monkeypatch.setattr(GoogleOAuthService, "build_authorization_url", _fake_build_authorization_url)

    response = client.post(
        "/api/v1/profile/me/google/connect",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["authorization_url"] == "https://accounts.google.com/mock-consent"


def test_google_disconnect_route_clears_connection(client, db_session: Session) -> None:
    token, therapist_email = _register(client)
    therapist = db_session.scalar(select(Therapist).where(Therapist.email == therapist_email))
    assert therapist is not None

    therapist.google_oauth_subject = "oauth@workspace.com"
    therapist.google_oauth_access_token = "access-token"
    therapist.google_oauth_refresh_token = "refresh-token"
    therapist.google_oauth_scopes = "scope1 scope2"
    db_session.add(therapist)
    db_session.commit()

    response = client.post(
        "/api/v1/profile/me/google/disconnect",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["google_oauth_connected"] is False
    assert payload["google_oauth_email"] is None


def test_google_callback_redirects_back_to_profile(client, db_session: Session, monkeypatch) -> None:
    _, therapist_email = _register(client)
    therapist = db_session.scalar(select(Therapist).where(Therapist.email == therapist_email))
    assert therapist is not None

    def _fake_complete_authorization(self, *, code: str, state: str):
        assert code == "mock-code"
        assert state == "mock-state"
        therapist.google_oauth_subject = "oauth@workspace.com"
        therapist.google_oauth_refresh_token = "refresh-token"
        self.db.add(therapist)
        return therapist, GoogleOAuthCallbackResult(
            connected_email="oauth@workspace.com",
            granted_scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )

    monkeypatch.setattr(GoogleOAuthService, "complete_authorization", _fake_complete_authorization)

    response = client.get(
        "/api/v1/profile/google/callback?code=mock-code&state=mock-state",
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    assert location.endswith("/profile?google=connected")

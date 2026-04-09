from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Therapist


class _StubMicrosoftOAuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_authorization_url(self, therapist: Therapist) -> str:
        assert therapist.email == "ms@clinic.com"
        return "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?stub=true"

    def disconnect(self, therapist: Therapist) -> Therapist:
        therapist.microsoft_oauth_refresh_token = None
        therapist.microsoft_oauth_subject = None
        self.db.add(therapist)
        return therapist

    def complete_authorization(self, *, code: str, state: str):
        assert code == "abc123"
        assert state == "state-token"
        therapist = self.db.scalar(select(Therapist).where(Therapist.email == "ms@clinic.com"))
        assert therapist is not None
        therapist.microsoft_oauth_refresh_token = "refresh-token"
        therapist.microsoft_oauth_subject = "ms-user@tenant.com"
        self.db.add(therapist)

        class _Result:
            connected_email = "ms-user@tenant.com"
            granted_scopes = ["Calendars.Read", "OnlineMeetings.Read"]

        return therapist, _Result()


def _register_and_authenticate(client) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Microsoft Demo",
            "email": "ms@clinic.com",
            "password": "supersecure123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_microsoft_connect_and_disconnect_routes(client, monkeypatch) -> None:
    token = _register_and_authenticate(client)
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr("app.api.routes.profile.MicrosoftOAuthService", _StubMicrosoftOAuthService)

    connect = client.post("/api/v1/profile/me/microsoft/connect", headers=headers)
    assert connect.status_code == 200
    assert connect.json()["authorization_url"].startswith("https://login.microsoftonline.com")

    disconnect = client.post("/api/v1/profile/me/microsoft/disconnect", headers=headers)
    assert disconnect.status_code == 200
    assert disconnect.json()["microsoft_oauth_connected"] is False


def test_microsoft_callback_redirects_to_profile(client, monkeypatch) -> None:
    _register_and_authenticate(client)
    monkeypatch.setattr("app.api.routes.profile.MicrosoftOAuthService", _StubMicrosoftOAuthService)

    response = client.get(
        "/api/v1/profile/microsoft/callback",
        params={"code": "abc123", "state": "state-token"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    assert "microsoft=connected" in response.headers["location"]

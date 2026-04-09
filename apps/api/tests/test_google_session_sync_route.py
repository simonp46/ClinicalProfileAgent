from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes import sessions as sessions_route
from app.domain.models import Therapist


class _StubGoogleSessionSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sync_for_therapist(self, therapist: Therapist, *, limit: int = 20):
        assert therapist.email == "sync@clinic.com"
        assert limit == 20

        class _Result:
            @staticmethod
            def as_dict() -> dict[str, int]:
                return {
                    "created_sessions": 1,
                    "updated_sessions": 2,
                    "processed_transcripts": 1,
                    "skipped_events": 0,
                }

        return _Result()


def _register_and_authenticate(client) -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Sync Demo",
            "email": "sync@clinic.com",
            "password": "supersecure123",
            "google_account_email": "sync@workspace.com",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["access_token"], "sync@clinic.com"


def test_sync_google_sessions_returns_counts(client, db_session: Session, monkeypatch) -> None:
    token, therapist_email = _register_and_authenticate(client)

    therapist = db_session.scalar(select(Therapist).where(Therapist.email == therapist_email))
    assert therapist is not None

    monkeypatch.setattr(sessions_route, "GoogleSessionSyncService", _StubGoogleSessionSyncService)

    response = client.post(
        "/api/v1/sessions/sync-google",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "created_sessions": 1,
        "updated_sessions": 2,
        "processed_transcripts": 1,
        "skipped_events": 0,
    }


def test_sync_google_sessions_surfaces_sync_errors(client, monkeypatch) -> None:
    token, _ = _register_and_authenticate(client)

    class _FailingService:
        def __init__(self, db: Session) -> None:
            self.db = db

        def sync_for_therapist(self, therapist: Therapist, *, limit: int = 20):
            _ = therapist
            _ = limit
            raise sessions_route.GoogleSessionSyncError("Google no conectado")

    monkeypatch.setattr(sessions_route, "GoogleSessionSyncService", _FailingService)

    response = client.post(
        "/api/v1/sessions/sync-google",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Google no conectado"

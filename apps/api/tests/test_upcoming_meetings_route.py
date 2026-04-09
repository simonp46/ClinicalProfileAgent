from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes import sessions as sessions_route
from app.domain.models import Patient, Session as SessionModel, Therapist


class _StubCalendarAdapter:
    def list_upcoming_meetings(self, *, limit: int = 5):
        assert limit == 5
        return [
            {
                "event_id": "evt-1",
                "title": "Control respiratorio semanal",
                "description": "Seguimiento de tecnica diafragmatica.",
                "start_at": "2026-04-08T15:00:00Z",
                "end_at": "2026-04-08T15:45:00Z",
                "meeting_url": "https://meet.google.com/abc-defg-hij",
                "calendar_html_link": "https://calendar.google.com/event?eid=evt-1",
                "linked_session_id": None,
                "source": "google_calendar",
            }
        ]


def _register_and_authenticate(client) -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Agenda Demo",
            "email": "agenda@clinic.com",
            "password": "supersecure123",
            "google_account_email": "agenda@workspace.com",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["access_token"], "agenda@clinic.com"


def test_upcoming_meetings_returns_google_calendar_data(client, db_session: Session, monkeypatch) -> None:
    token, therapist_email = _register_and_authenticate(client)

    therapist = db_session.scalar(select(Therapist).where(Therapist.email == therapist_email))
    assert therapist is not None

    def _build_calendar_adapter(**kwargs):
        assert kwargs["therapist_id"] == therapist.id
        assert kwargs["therapist"] == therapist
        assert kwargs["impersonated_user"] == therapist.google_account_email
        return _StubCalendarAdapter()

    monkeypatch.setattr(sessions_route, "build_calendar_adapter", _build_calendar_adapter)

    response = client.get(
        "/api/v1/sessions/upcoming-meetings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Control respiratorio semanal"
    assert items[0]["description"] == "Seguimiento de tecnica diafragmatica."
    assert items[0]["source"] == "google_calendar"


def test_upcoming_meetings_falls_back_to_future_sessions(client, db_session: Session, monkeypatch) -> None:
    token, therapist_email = _register_and_authenticate(client)

    therapist = db_session.scalar(select(Therapist).where(Therapist.email == therapist_email))
    assert therapist is not None

    patient = Patient(
        first_name="Lucia",
        last_name="Ramirez",
        consent_reference="CONS-001",
    )
    db_session.add(patient)
    db_session.flush()

    session = SessionModel(
        therapist_id=therapist.id,
        patient_id=patient.id,
        session_started_at=datetime.now(UTC) + timedelta(minutes=10),
        session_ended_at=datetime.now(UTC) + timedelta(minutes=55),
        google_meet_space_name="respira-demo-space",
    )
    db_session.add(session)
    db_session.commit()

    def _boom(**kwargs):
        _ = kwargs
        raise sessions_route.CalendarAdapterError("calendar unavailable")

    monkeypatch.setattr(sessions_route, "build_calendar_adapter", _boom)

    response = client.get(
        "/api/v1/sessions/upcoming-meetings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert any(item["title"] == "Consulta con Lucia Ramirez" for item in items)
    match = next(item for item in items if item["title"] == "Consulta con Lucia Ramirez")
    assert match["description"] == "Espacio Meet: respira-demo-space | Consentimiento: CONS-001"
    assert match["linked_session_id"] == session.id
    assert match["source"] == "internal_demo"

"""Google Calendar adapter with local fallback for upcoming meetings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.domain.enums import SessionStatus
from app.domain.models import Session as SessionModel, Therapist
from app.infrastructure.adapters.google_workspace_auth import build_google_credentials, has_google_oauth_connection


class CalendarAdapterError(Exception):
    """Raised when upcoming meetings cannot be loaded."""


class BaseCalendarAdapter(ABC):
    @abstractmethod
    def list_upcoming_meetings(self, *, limit: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError


class MockCalendarAdapter(BaseCalendarAdapter):
    """Local fallback using future scheduled sessions for the therapist."""

    def __init__(self, *, db: Session, therapist_id: str) -> None:
        self.db = db
        self.therapist_id = therapist_id

    def list_upcoming_meetings(self, *, limit: int = 5) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        query = (
            select(SessionModel)
            .where(
                SessionModel.therapist_id == self.therapist_id,
                SessionModel.session_started_at.is_not(None),
                SessionModel.session_started_at >= now,
                SessionModel.status == SessionStatus.scheduled,
            )
            .options(joinedload(SessionModel.patient))
            .order_by(SessionModel.session_started_at.asc())
            .limit(limit)
        )
        sessions = list(self.db.scalars(query).unique().all())

        items: list[dict[str, Any]] = []
        for session in sessions:
            patient = session.patient
            patient_name = (
                f"{patient.first_name} {patient.last_name}".strip()
                if patient and (patient.first_name or patient.last_name)
                else "Paciente"
            )
            description_parts = []
            if session.google_meet_space_name:
                description_parts.append(f"Espacio Meet: {session.google_meet_space_name}")
            if patient and patient.consent_reference:
                description_parts.append(f"Consentimiento: {patient.consent_reference}")

            items.append(
                {
                    "event_id": session.calendar_event_id or session.id,
                    "title": f"Consulta con {patient_name}",
                    "description": " | ".join(description_parts) or None,
                    "start_at": session.session_started_at.isoformat() if session.session_started_at else None,
                    "end_at": session.session_ended_at.isoformat() if session.session_ended_at else None,
                    "meeting_url": None,
                    "calendar_html_link": None,
                    "linked_session_id": session.id,
                    "linked_patient_name": patient_name,
                    "source": "internal_demo",
                }
            )
        return items


class GoogleCalendarAdapter(BaseCalendarAdapter):
    """Real Google Calendar adapter using delegated Workspace credentials."""

    def __init__(self, *, therapist: Therapist | None = None, impersonated_user: str | None = None) -> None:
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        try:
            creds = build_google_credentials(scopes=scopes, therapist=therapist, impersonated_user=impersonated_user)
        except ValueError as exc:
            raise CalendarAdapterError(str(exc)) from exc

        self.calendar_service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def list_upcoming_meetings(self, *, limit: int = 5) -> list[dict[str, Any]]:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        try:
            response = (
                self.calendar_service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=limit,
                    fields=(
                        "items(id,summary,description,htmlLink,hangoutLink,"
                        "start(dateTime,date),end(dateTime,date),status)"
                    ),
                )
                .execute()
            )
        except Exception as exc:
            raise CalendarAdapterError("Could not load upcoming Google Calendar events.") from exc

        items: list[dict[str, Any]] = []
        for event in response.get("items", []):
            if str(event.get("status") or "").lower() == "cancelled":
                continue

            start = event.get("start") or {}
            end = event.get("end") or {}
            items.append(
                {
                    "event_id": event.get("id"),
                    "title": str(event.get("summary") or "Consulta programada"),
                    "description": str(event.get("description") or "").strip() or None,
                    "start_at": start.get("dateTime") or start.get("date"),
                    "end_at": end.get("dateTime") or end.get("date"),
                    "meeting_url": event.get("hangoutLink"),
                    "calendar_html_link": event.get("htmlLink"),
                    "linked_session_id": None,
                    "source": "google_calendar",
                }
            )
        return items


def build_calendar_adapter(
    *,
    db: Session,
    therapist_id: str,
    therapist: Therapist | None = None,
    impersonated_user: str | None = None,
) -> BaseCalendarAdapter:
    if settings.use_mock_google:
        return MockCalendarAdapter(db=db, therapist_id=therapist_id)
    if not settings.google_service_account_file and not has_google_oauth_connection(therapist):
        return MockCalendarAdapter(db=db, therapist_id=therapist_id)
    return GoogleCalendarAdapter(therapist=therapist, impersonated_user=impersonated_user)

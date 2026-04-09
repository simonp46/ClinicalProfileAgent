"""Synchronize Google Calendar + Meet activity into internal sessions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.application.services.audit_service import AuditService
from app.application.services.pipeline_service import PipelineService
from app.application.services.session_service import SessionService
from app.domain.enums import AuditActorType, SessionSource
from app.domain.models import Session as SessionModel
from app.domain.models import Therapist
from app.domain.schemas import PatientCreate, SessionCreate
from app.infrastructure.adapters.google_workspace_auth import (
    GoogleWorkspaceAuthError,
    build_google_credentials,
    has_google_oauth_connection,
)


class GoogleSessionSyncError(ValueError):
    """Raised when a therapist Google session sync cannot run."""


@dataclass
class GoogleSessionSyncResult:
    created_sessions: int = 0
    updated_sessions: int = 0
    processed_transcripts: int = 0
    skipped_events: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "created_sessions": self.created_sessions,
            "updated_sessions": self.updated_sessions,
            "processed_transcripts": self.processed_transcripts,
            "skipped_events": self.skipped_events,
        }


class GoogleSessionSyncService:
    """Catch up real Google Meet sessions from the therapist's connected account."""

    _CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    _MEET_SCOPES = [
        "https://www.googleapis.com/auth/meetings.space.readonly",
        "https://www.googleapis.com/auth/documents.readonly",
    ]
    _FUTURE_LOOKAHEAD_DAYS = 14
    _PAST_LOOKBACK_DAYS = 2

    def __init__(self, db: Session) -> None:
        self.db = db
        self.session_service = SessionService(db)
        self.audit = AuditService(db)

    def sync_for_therapist(
        self,
        therapist: Therapist,
        *,
        limit: int = 20,
    ) -> GoogleSessionSyncResult:
        if not therapist.google_account_email and not has_google_oauth_connection(therapist):
            raise GoogleSessionSyncError(
                "Conecta Google desde el perfil del terapeuta para sincronizar reuniones reales."
            )

        try:
            calendar_credentials = build_google_credentials(
                scopes=self._CALENDAR_SCOPES,
                therapist=therapist,
                impersonated_user=therapist.google_account_email,
            )
            meet_credentials = build_google_credentials(
                scopes=self._MEET_SCOPES,
                therapist=therapist,
                impersonated_user=therapist.google_account_email,
            )
        except GoogleWorkspaceAuthError as exc:
            raise GoogleSessionSyncError(str(exc)) from exc

        from googleapiclient.discovery import build

        calendar_service = build(
            "calendar",
            "v3",
            credentials=calendar_credentials,
            cache_discovery=False,
        )
        meet_service = build(
            "meet",
            "v2",
            credentials=meet_credentials,
            cache_discovery=False,
        )

        now = datetime.now(UTC)
        time_min = (
            (now - timedelta(days=self._PAST_LOOKBACK_DAYS)).isoformat().replace("+00:00", "Z")
        )
        time_max = (
            (now + timedelta(days=self._FUTURE_LOOKAHEAD_DAYS)).isoformat().replace("+00:00", "Z")
        )

        response = (
            calendar_service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=limit,
                fields=(
                    "items(id,summary,description,htmlLink,hangoutLink,status,"
                    "conferenceData(conferenceId,entryPoints(uri,meetingCode)),"
                    "start(dateTime,date),end(dateTime,date))"
                ),
            )
            .execute()
        )

        result = GoogleSessionSyncResult()
        pipeline = PipelineService(self.db)

        for event in response.get("items", []):
            if str(event.get("status") or "").lower() == "cancelled":
                continue

            event_id = str(event.get("id") or "").strip()
            if not event_id:
                result.skipped_events += 1
                continue

            default_title = "Consulta Google Meet"
            title = str(event.get("summary") or default_title).strip() or default_title
            start_at = self._parse_calendar_datetime(event.get("start") or {})
            end_at = self._parse_calendar_datetime(event.get("end") or {})
            meeting_url = self._extract_meeting_url(event)
            meeting_code = self._extract_meeting_code(event, meeting_url)

            if not meeting_code and not meeting_url:
                result.skipped_events += 1
                continue

            session = self.db.scalar(
                select(SessionModel)
                .where(
                    SessionModel.therapist_id == therapist.id,
                    SessionModel.calendar_event_id == event_id,
                )
                .options(
                    joinedload(SessionModel.patient),
                    joinedload(SessionModel.transcript),
                    joinedload(SessionModel.therapist),
                )
            )

            created = False
            if session is None:
                first_name, last_name = self._derive_patient_name(title)
                session = self.session_service.create_session(
                    SessionCreate(
                        therapist_id=therapist.id,
                        patient=PatientCreate(
                            first_name=first_name,
                            last_name=last_name,
                            notes=self._build_patient_note_from_event(event),
                        ),
                        calendar_event_id=event_id,
                        session_started_at=start_at,
                        session_ended_at=end_at,
                        source=SessionSource.google_meet,
                    )
                )
                created = True
            else:
                session.session_started_at = start_at or session.session_started_at
                session.session_ended_at = end_at or session.session_ended_at
                self.db.add(session)

            if created:
                result.created_sessions += 1
                self._log_sync(
                    session,
                    therapist.id,
                    "session.synced_from_google_calendar.created",
                    {"calendar_event_id": event_id, "title": title},
                )
            else:
                result.updated_sessions += 1
                self._log_sync(
                    session,
                    therapist.id,
                    "session.synced_from_google_calendar.updated",
                    {"calendar_event_id": event_id, "title": title},
                )

            conference_record = None
            if meeting_code:
                conference_record = self._find_conference_record(
                    meet_service=meet_service,
                    meeting_code=meeting_code,
                    scheduled_start=start_at,
                )

            if conference_record:
                record_name = str(
                    conference_record.get("name") or session.google_conference_record_name or ""
                ).strip()
                space_name = self._extract_space_name(conference_record)
                record_start = self._parse_google_timestamp(conference_record.get("startTime"))
                record_end = self._parse_google_timestamp(conference_record.get("endTime"))

                if record_name:
                    session.google_conference_record_name = record_name
                if space_name:
                    session.google_meet_space_name = space_name
                session.session_started_at = record_start or session.session_started_at
                session.session_ended_at = record_end or session.session_ended_at
                self.db.add(session)

            ready_transcript_name = self._find_ready_transcript_name(
                meet_service,
                session.google_conference_record_name,
            )

            if ready_transcript_name and not session.transcript:
                try:
                    pipeline.ingest_from_meet(session, transcript_name=ready_transcript_name)
                    pipeline.generate_draft(session, regenerate=False)
                    result.processed_transcripts += 1
                    self._log_sync(
                        session,
                        therapist.id,
                        "session.synced_from_google_meet.transcript_processed",
                        {
                            "calendar_event_id": event_id,
                            "title": title,
                            "transcript_name": ready_transcript_name,
                        },
                    )
                except Exception as exc:
                    self._log_sync(
                        session,
                        therapist.id,
                        "session.synced_from_google_meet.transcript_failed",
                        {
                            "calendar_event_id": event_id,
                            "title": title,
                            "transcript_name": ready_transcript_name,
                            "error": str(exc),
                        },
                    )
            elif session.google_conference_record_name and not session.transcript:
                self._log_sync(
                    session,
                    therapist.id,
                    "session.synced_from_google_meet.transcript_pending",
                    {
                        "calendar_event_id": event_id,
                        "title": title,
                    },
                )

        return result

    def _find_conference_record(
        self,
        *,
        meet_service: Any,
        meeting_code: str,
        scheduled_start: datetime | None,
    ) -> dict[str, Any] | None:
        normalized_code = meeting_code.lower()
        response = (
            meet_service.conferenceRecords()
            .list(
                pageSize=20,
                filter=f'space.meeting_code = "{normalized_code}"',
            )
            .execute()
        )
        records = response.get("conferenceRecords", []) if isinstance(response, dict) else []

        if not records:
            return None

        if scheduled_start is None:
            records.sort(
                key=lambda item: item.get("startTime")
                or item.get("endTime")
                or item.get("name")
                or "",
                reverse=True,
            )
            return records[0]

        def _distance(record: dict[str, Any]) -> float:
            record_start = self._parse_google_timestamp(record.get("startTime"))
            if record_start is None:
                return float("inf")
            return abs((record_start - scheduled_start).total_seconds())

        records.sort(key=_distance)
        return records[0]

    def _find_ready_transcript_name(
        self,
        meet_service: Any,
        conference_record_name: str | None,
    ) -> str | None:
        if not conference_record_name:
            return None

        try:
            response = (
                meet_service.conferenceRecords()
                .transcripts()
                .list(parent=conference_record_name, pageSize=10)
                .execute()
            )
        except Exception:
            return None

        transcripts = response.get("transcripts", []) if isinstance(response, dict) else []
        generated = [
            item
            for item in transcripts
            if str(item.get("state") or "").strip().upper() == "FILE_GENERATED"
        ]
        if not generated:
            return None

        generated.sort(
            key=lambda item: item.get("endTime") or item.get("startTime") or item.get("name") or ""
        )
        transcript_name = str(generated[-1].get("name") or "").strip()
        return transcript_name or None

    def _extract_meeting_url(self, event: dict[str, Any]) -> str | None:
        direct = str(event.get("hangoutLink") or "").strip()
        if direct:
            return direct

        conference_data = event.get("conferenceData") if isinstance(event, dict) else None
        entry_points = (
            conference_data.get("entryPoints", []) if isinstance(conference_data, dict) else []
        )
        for entry in entry_points:
            uri = str(entry.get("uri") or "").strip()
            if uri:
                return uri
        return None

    def _extract_meeting_code(self, event: dict[str, Any], meeting_url: str | None) -> str | None:
        conference_data = event.get("conferenceData") if isinstance(event, dict) else None
        entry_points = (
            conference_data.get("entryPoints", []) if isinstance(conference_data, dict) else []
        )
        for entry in entry_points:
            code = str(entry.get("meetingCode") or "").strip()
            if code:
                return code.lower()

        if meeting_url:
            match = re.search(
                r"meet\.google\.com/([a-z]{3}-[a-z]{4}-[a-z]{3})",
                meeting_url,
                re.IGNORECASE,
            )
            if match:
                return match.group(1).lower()
        return None

    def _derive_patient_name(self, title: str) -> tuple[str, str]:
        cleaned = re.sub(
            r"^(consulta|sesion|terapia|reunion|meet|videollamada)\s+(con\s+)?",
            "",
            title.strip(),
            flags=re.IGNORECASE,
        ).strip(" -:")
        if not cleaned:
            return ("Paciente", "Pendiente")

        cleaned = re.sub(r"\s+", " ", cleaned)
        parts = cleaned.split(" ", 1)
        if len(parts) == 1:
            return (parts[0][:80], "Pendiente")
        return (parts[0][:80], parts[1][:120])

    def _build_patient_note_from_event(self, event: dict[str, Any]) -> str | None:
        description = str(event.get("description") or "").strip()
        html_link = str(event.get("htmlLink") or "").strip()
        note_parts = []
        if description:
            note_parts.append(f"Descripcion del evento de Google Calendar: {description}")
        if html_link:
            note_parts.append(f"Evento fuente: {html_link}")
        return " | ".join(note_parts) or None

    def _extract_space_name(self, conference_record: dict[str, Any]) -> str | None:
        space = conference_record.get("space")
        if isinstance(space, dict):
            return str(space.get("name") or "").strip() or None
        if isinstance(space, str):
            return space.strip() or None
        return None

    def _parse_calendar_datetime(self, payload: dict[str, Any]) -> datetime | None:
        value = payload.get("dateTime") or payload.get("date")
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        if len(text) == 10:
            return datetime.fromisoformat(f"{text}T00:00:00+00:00")
        return self._parse_google_timestamp(text)

    def _parse_google_timestamp(self, value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _log_sync(
        self,
        session: SessionModel,
        actor_id: str,
        action: str,
        metadata: dict[str, Any],
    ) -> None:
        self.audit.log(
            actor_type=AuditActorType.therapist,
            actor_id=actor_id,
            entity_type="session",
            entity_id=session.id,
            action=action,
            metadata=metadata,
        )

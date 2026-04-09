"""Google Meet transcript adapter."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.domain.models import Session, Therapist
from app.domain.schemas import TranscriptIngestRequest, TranscriptSegmentIn
from app.infrastructure.adapters.google_workspace_auth import build_google_credentials, has_google_oauth_connection


class MeetAdapterError(Exception):
    """Raised when transcript retrieval fails."""


class BaseMeetAdapter(ABC):
    @abstractmethod
    def fetch_transcript(self, session: Session, *, transcript_name: str | None = None) -> TranscriptIngestRequest:
        raise NotImplementedError


class MockMeetAdapter(BaseMeetAdapter):
    """Fixture-backed transcript adapter for local demo."""

    def __init__(self, fixture_path: str | None = None) -> None:
        self.fixture_path = Path(
            fixture_path or Path(__file__).resolve().parents[3] / "fixtures" / "sample_transcript.json"
        )

    def fetch_transcript(self, session: Session, *, transcript_name: str | None = None) -> TranscriptIngestRequest:
        _ = session
        _ = transcript_name
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8-sig"))
        return TranscriptIngestRequest.model_validate(payload)


class GoogleMeetAdapter(BaseMeetAdapter):
    """Real Google Meet adapter using Meet transcripts and Google Docs transcript fallback."""

    def __init__(self, *, therapist: Therapist | None = None, impersonated_user: str | None = None) -> None:
        from googleapiclient.discovery import build

        if not settings.google_transcript_fetch_enabled:
            raise MeetAdapterError(
                "GOOGLE_TRANSCRIPT_FETCH_ENABLED must be true to fetch real Google Meet transcripts."
            )

        scopes = [
            "https://www.googleapis.com/auth/meetings.space.readonly",
            "https://www.googleapis.com/auth/documents.readonly",
        ]
        try:
            creds = build_google_credentials(scopes=scopes, therapist=therapist, impersonated_user=impersonated_user)
        except ValueError as exc:
            raise MeetAdapterError(str(exc)) from exc

        self.meet_service = build("meet", "v2", credentials=creds, cache_discovery=False)
        self.docs_service = build("docs", "v1", credentials=creds, cache_discovery=False)

    def fetch_transcript(self, session: Session, *, transcript_name: str | None = None) -> TranscriptIngestRequest:
        resolved_name = self._resolve_transcript_name(session, transcript_name=transcript_name)
        transcript_meta = self._get_transcript(resolved_name)
        segments = self._fetch_transcript_entries(resolved_name)

        docs_destination = transcript_meta.get("docsDestination") if isinstance(transcript_meta, dict) else None
        if not segments and isinstance(docs_destination, dict):
            doc_id = self._extract_doc_id(str(docs_destination.get("document") or ""))
            if doc_id:
                segments = self._fetch_segments_from_google_doc(doc_id)

        if not segments:
            raise MeetAdapterError(
                "Google Meet returned no transcript entries. Verify the meeting transcript exists and is accessible "
                "to the configured Workspace account."
            )

        docs_uri = None
        if isinstance(docs_destination, dict):
            document_ref = str(docs_destination.get("document") or "").strip()
            if document_ref:
                doc_id = self._extract_doc_id(document_ref)
                docs_uri = f"https://docs.google.com/document/d/{doc_id}/edit" if doc_id else document_ref

        return TranscriptIngestRequest(
            google_transcript_name=resolved_name,
            google_docs_uri=docs_uri,
            language_code=self._resolve_language_code(segments, transcript_meta),
            segments=segments,
        )

    def _resolve_transcript_name(self, session: Session, *, transcript_name: str | None) -> str:
        candidate = (transcript_name or "").strip()
        if candidate:
            return candidate

        if session.transcript and session.transcript.google_transcript_name:
            return session.transcript.google_transcript_name

        conference_record_name = (session.google_conference_record_name or "").strip()
        if conference_record_name:
            return self._latest_transcript_name(conference_record_name)

        raise MeetAdapterError(
            "No transcript resource name was provided. Store google_conference_record_name on the session or send "
            "transcriptName from the Google Workspace event."
        )

    def _latest_transcript_name(self, conference_record_name: str) -> str:
        page_token: str | None = None
        transcripts: list[dict[str, Any]] = []

        while True:
            request = self.meet_service.conferenceRecords().transcripts().list(
                parent=conference_record_name,
                pageSize=100,
                pageToken=page_token,
            )
            response = request.execute()
            transcripts.extend(response.get("transcripts", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        if not transcripts:
            raise MeetAdapterError(f"No transcripts found for conference record {conference_record_name}.")

        transcripts.sort(key=lambda item: item.get("endTime") or item.get("startTime") or item.get("name") or "")
        return str(transcripts[-1]["name"])

    def _get_transcript(self, transcript_name: str) -> dict[str, Any]:
        return self.meet_service.conferenceRecords().transcripts().get(name=transcript_name).execute()

    def _fetch_transcript_entries(self, transcript_name: str) -> list[TranscriptSegmentIn]:
        page_token: str | None = None
        segments: list[TranscriptSegmentIn] = []
        participant_cache: dict[str, str] = {}
        sequence = 1

        while True:
            request = self.meet_service.conferenceRecords().transcripts().entries().list(
                parent=transcript_name,
                pageSize=200,
                pageToken=page_token,
            )
            response = request.execute()
            entries = response.get("transcriptEntries", [])

            for item in entries:
                participant_ref = str(item.get("participant") or "").strip() or None
                speaker_label = self._resolve_participant_label(participant_ref, participant_cache)
                segments.append(
                    TranscriptSegmentIn(
                        sequence_no=sequence,
                        speaker_label=speaker_label,
                        original_participant_ref=participant_ref,
                        text=str(item.get("text") or "").strip(),
                        start_time=self._parse_google_timestamp(item.get("startTime")),
                        end_time=self._parse_google_timestamp(item.get("endTime")),
                    )
                )
                sequence += 1

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return [segment for segment in segments if segment.text]

    def _resolve_participant_label(self, participant_ref: str | None, cache: dict[str, str]) -> str:
        if not participant_ref:
            return "Desconocido"
        if participant_ref in cache:
            return cache[participant_ref]

        try:
            payload = self.meet_service.conferenceRecords().participants().get(name=participant_ref).execute()
        except Exception:
            cache[participant_ref] = participant_ref
            return participant_ref

        signed_in = None
        if isinstance(payload, dict):
            signed_in = payload.get("signedInUser") or payload.get("signedinUser")
        anonymous = payload.get("anonymousUser") if isinstance(payload, dict) else None
        phone_user = payload.get("phoneUser") if isinstance(payload, dict) else None

        display_name = ""
        if isinstance(signed_in, dict):
            display_name = str(signed_in.get("displayName") or signed_in.get("user") or "")
        elif isinstance(anonymous, dict):
            display_name = str(anonymous.get("displayName") or "")
        elif isinstance(phone_user, dict):
            display_name = str(phone_user.get("displayName") or phone_user.get("formattedPhoneNumber") or "")

        label = display_name.strip() or participant_ref
        cache[participant_ref] = label
        return label

    def _fetch_segments_from_google_doc(self, doc_id: str) -> list[TranscriptSegmentIn]:
        document = self.docs_service.documents().get(documentId=doc_id).execute()
        body = document.get("body", {}) if isinstance(document, dict) else {}
        content = body.get("content", []) if isinstance(body, dict) else []

        segments: list[TranscriptSegmentIn] = []
        sequence = 1
        speaker_pattern = re.compile(r"^(?P<speaker>[^:]{2,80}):\s*(?P<text>.+)$")

        for block in content:
            paragraph = block.get("paragraph") if isinstance(block, dict) else None
            if not isinstance(paragraph, dict):
                continue

            text_runs: list[str] = []
            for element in paragraph.get("elements", []):
                text_run = element.get("textRun") if isinstance(element, dict) else None
                if isinstance(text_run, dict):
                    text_runs.append(str(text_run.get("content") or ""))

            line = "".join(text_runs).strip()
            if not line:
                continue

            match = speaker_pattern.match(line)
            if match:
                speaker_label = match.group("speaker").strip()
                text = match.group("text").strip()
            else:
                speaker_label = "Desconocido"
                text = line

            if not text:
                continue

            segments.append(
                TranscriptSegmentIn(
                    sequence_no=sequence,
                    speaker_label=speaker_label,
                    original_participant_ref=None,
                    text=text,
                    start_time=None,
                    end_time=None,
                )
            )
            sequence += 1

        return segments

    def _resolve_language_code(
        self,
        segments: list[TranscriptSegmentIn],
        transcript_meta: dict[str, Any],
    ) -> str:
        for item in segments:
            if item.start_time or item.end_time:
                break
        return str(transcript_meta.get("languageCode") or "es") if isinstance(transcript_meta, dict) else "es"

    def _extract_doc_id(self, value: str) -> str | None:
        if not value:
            return None
        match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", value)
        if match:
            return match.group(1)
        if value.startswith("documents/"):
            return value.split("/", 1)[1]
        return value if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", value) else None

    def _parse_google_timestamp(self, value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        return datetime.fromisoformat(text.replace("Z", "+00:00"))


def build_meet_adapter(*, therapist: Therapist | None = None, impersonated_user: str | None = None) -> BaseMeetAdapter:
    if settings.use_mock_google:
        return MockMeetAdapter()
    if not settings.google_service_account_file and not has_google_oauth_connection(therapist):
        return MockMeetAdapter()
    return GoogleMeetAdapter(therapist=therapist, impersonated_user=impersonated_user)

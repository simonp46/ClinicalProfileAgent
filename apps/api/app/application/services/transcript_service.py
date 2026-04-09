"""Transcript ingestion and normalization service."""

from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditService
from app.application.services.transcript_pipeline_types import TranscriptEntry
from app.domain.enums import AuditActorType
from app.domain.models import DeidentificationMap, Session as SessionModel, Transcript, TranscriptSegment
from app.domain.schemas import TranscriptIngestRequest
from app.infrastructure.adapters.deid_service import DeidentificationService
from app.infrastructure.adapters.transcript_normalizer import TranscriptNormalizer


class TranscriptService:
    """Process and persist transcript payloads."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.normalizer = TranscriptNormalizer()
        self.deidentifier = DeidentificationService()
        self.audit = AuditService(db)

    def ingest_transcript(self, session: SessionModel, payload: TranscriptIngestRequest) -> Transcript:
        entries = [
            TranscriptEntry(
                sequence_no=item.sequence_no,
                speaker_label=item.speaker_label,
                original_participant_ref=item.original_participant_ref,
                text=item.text,
                start_time=item.start_time,
                end_time=item.end_time,
            )
            for item in payload.segments
        ]

        normalized_entries = self.normalizer.normalize_entries(
            entries,
            therapist_name=session.therapist.full_name,
            patient_name=f"{session.patient.first_name} {session.patient.last_name}",
        )
        raw_text = self.normalizer.build_transcript_text(entries)
        normalized_text = self.normalizer.build_transcript_text(normalized_entries)

        deid_result = self.deidentifier.deidentify(
            normalized_text,
            known_names=[
                session.therapist.full_name,
                session.patient.first_name,
                session.patient.last_name,
                f"{session.patient.first_name} {session.patient.last_name}",
            ],
        )
        source_hash = self._hash_content(payload)

        transcript = self.db.scalar(select(Transcript).where(Transcript.session_id == session.id))
        if transcript is None:
            transcript = Transcript(
                session_id=session.id,
                google_transcript_name=payload.google_transcript_name,
                google_docs_uri=payload.google_docs_uri,
                language_code=payload.language_code,
                raw_text=raw_text,
                normalized_text=normalized_text,
                deidentified_text=deid_result.text,
                source_hash=source_hash,
            )
            self.db.add(transcript)
            self.db.flush()
        else:
            transcript.google_transcript_name = payload.google_transcript_name
            transcript.google_docs_uri = payload.google_docs_uri
            transcript.language_code = payload.language_code
            transcript.raw_text = raw_text
            transcript.normalized_text = normalized_text
            transcript.deidentified_text = deid_result.text
            transcript.source_hash = source_hash
            self.db.add(transcript)
            self.db.flush()

            self.db.execute(delete(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript.id))
            self.db.execute(
                delete(DeidentificationMap).where(DeidentificationMap.transcript_id == transcript.id)
            )

        self._persist_segments(transcript.id, normalized_entries)
        self._persist_mappings(transcript.id, deid_result.mappings)

        self.audit.log(
            actor_type=AuditActorType.system,
            entity_type="transcript",
            entity_id=transcript.id,
            action="transcript.ingested",
            metadata={
                "session_id": session.id,
                "segment_count": len(normalized_entries),
                "source_hash": source_hash,
            },
        )
        return transcript

    def _persist_segments(self, transcript_id: str, entries: list[TranscriptEntry]) -> None:
        for item in entries:
            self.db.add(
                TranscriptSegment(
                    transcript_id=transcript_id,
                    speaker_label=item.speaker_label,
                    original_participant_ref=item.original_participant_ref,
                    text=item.text,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    sequence_no=item.sequence_no,
                )
            )

    def _persist_mappings(self, transcript_id: str, mappings: list[object]) -> None:
        for mapping in mappings:
            self.db.add(
                DeidentificationMap(
                    transcript_id=transcript_id,
                    entity_type=mapping.entity_type,
                    placeholder=mapping.placeholder,
                    original_value=mapping.original_value,
                )
            )

    def _hash_content(self, payload: TranscriptIngestRequest) -> str:
        digest = hashlib.sha256()
        digest.update((payload.google_transcript_name or "").encode("utf-8"))
        digest.update((payload.google_docs_uri or "").encode("utf-8"))
        digest.update((payload.language_code or "").encode("utf-8"))
        for segment in payload.segments:
            digest.update(str(segment.sequence_no).encode("utf-8"))
            digest.update(segment.speaker_label.encode("utf-8"))
            digest.update(segment.text.encode("utf-8"))
            if segment.start_time:
                digest.update(segment.start_time.isoformat().encode("utf-8"))
            if segment.end_time:
                digest.update(segment.end_time.isoformat().encode("utf-8"))
        return digest.hexdigest()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)
"""End-to-end processing pipeline orchestration."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.clinical_draft_service import ClinicalDraftService
from app.application.services.document_service import DocumentGenerationService
from app.application.services.job_service import ProcessingJobService
from app.application.services.session_service import SessionService
from app.application.services.transcript_service import TranscriptService
from app.domain.enums import ProcessingJobType, SessionStatus
from app.domain.models import ClinicalDraft, GeneratedDocument, Session as SessionModel
from app.infrastructure.adapters.google_meet_adapter import BaseMeetAdapter, build_meet_adapter


class PipelineService:
    """Coordinate transcript ingestion, draft generation, and docs creation."""

    def __init__(self, db: Session, meet_adapter: BaseMeetAdapter | None = None) -> None:
        self.db = db
        self.meet_adapter = meet_adapter
        self.session_service = SessionService(db)
        self.transcript_service = TranscriptService(db)
        self.draft_service = ClinicalDraftService(db)
        self.doc_service = DocumentGenerationService(db)
        self.job_service = ProcessingJobService(db)

    def ingest_from_meet(self, session: SessionModel, transcript_name: str | None = None) -> str:
        job = self.job_service.create_job(session.id, ProcessingJobType.ingest_transcript)
        self.job_service.mark_running(job)
        session.status = SessionStatus.processing
        self.db.add(session)

        try:
            adapter = self.meet_adapter or build_meet_adapter(
                therapist=session.therapist,
                impersonated_user=session.therapist.google_account_email if session.therapist else None,
            )
            payload = adapter.fetch_transcript(session, transcript_name=transcript_name)
            transcript = self.transcript_service.ingest_transcript(session, payload)
            self.job_service.mark_success(job)
            return transcript.id
        except Exception as exc:
            session.status = SessionStatus.failed
            self.db.add(session)
            self.job_service.mark_failed(job, str(exc))
            raise

    def generate_draft(self, session: SessionModel, *, regenerate: bool = False) -> ClinicalDraft:
        job = self.job_service.create_job(session.id, ProcessingJobType.generate_draft)
        self.job_service.mark_running(job)
        session.status = SessionStatus.processing
        self.db.add(session)

        try:
            draft = self.draft_service.generate_for_session(session, regenerate=regenerate)
            self.job_service.mark_success(job)
            return draft
        except Exception as exc:
            session.status = SessionStatus.failed
            self.db.add(session)
            self.job_service.mark_failed(job, str(exc))
            raise

    def create_document(self, session: SessionModel, draft: ClinicalDraft) -> GeneratedDocument:
        job = self.job_service.create_job(session.id, ProcessingJobType.create_doc)
        self.job_service.mark_running(job)
        try:
            document = self.doc_service.create_document(session, draft)
            self.job_service.mark_success(job)
            return document
        except Exception as exc:
            self.job_service.mark_failed(job, str(exc))
            raise

    def export_docx(self, document: GeneratedDocument) -> GeneratedDocument:
        job = self.job_service.create_job(document.session_id, ProcessingJobType.export_docx)
        self.job_service.mark_running(job)
        try:
            exported = self.doc_service.export_docx(document)
            self.job_service.mark_success(job)
            return exported
        except Exception as exc:
            self.job_service.mark_failed(job, str(exc))
            raise

    def get_session(self, session_id: str) -> SessionModel | None:
        return self.db.scalar(select(SessionModel).where(SessionModel.id == session_id))

"""Celery tasks for async processing."""

from __future__ import annotations

from celery import shared_task
from sqlalchemy import select

from app.application.services.pipeline_service import PipelineService
from app.db.session import SessionLocal
from app.domain.models import ClinicalDraft, GeneratedDocument, Session as SessionModel


@shared_task(bind=True, max_retries=3)
def process_session_task(self, session_id: str, transcript_name: str | None = None) -> dict[str, str]:
    db = SessionLocal()
    try:
        session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
        if session is None:
            return {"status": "error", "message": "session_not_found"}
        pipeline = PipelineService(db)
        pipeline.ingest_from_meet(session, transcript_name=transcript_name)
        db.commit()
        return {"status": "ok", "session_id": session_id}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def generate_draft_task(self, session_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
        if session is None:
            return {"status": "error", "message": "session_not_found"}
        pipeline = PipelineService(db)
        draft = pipeline.generate_draft(session, regenerate=False)
        db.commit()
        return {"status": "ok", "draft_id": draft.id}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def regenerate_draft_task(self, session_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
        if session is None:
            return {"status": "error", "message": "session_not_found"}
        pipeline = PipelineService(db)
        draft = pipeline.generate_draft(session, regenerate=True)
        db.commit()
        return {"status": "ok", "draft_id": draft.id}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def process_and_generate_task(
    self, session_id: str, transcript_name: str | None = None
) -> dict[str, str]:
    db = SessionLocal()
    try:
        session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
        if session is None:
            return {"status": "error", "message": "session_not_found"}
        pipeline = PipelineService(db)
        pipeline.ingest_from_meet(session, transcript_name=transcript_name)
        draft = pipeline.generate_draft(session, regenerate=False)
        db.commit()
        return {"status": "ok", "draft_id": draft.id}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def create_doc_task(self, draft_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        draft = db.scalar(select(ClinicalDraft).where(ClinicalDraft.id == draft_id))
        if draft is None:
            return {"status": "error", "message": "draft_not_found"}

        session = db.scalar(select(SessionModel).where(SessionModel.id == draft.session_id))
        if session is None:
            return {"status": "error", "message": "session_not_found"}

        pipeline = PipelineService(db)
        document = pipeline.create_document(session, draft)
        db.commit()
        return {"status": "ok", "document_id": document.id}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def export_docx_task(self, document_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        document = db.scalar(select(GeneratedDocument).where(GeneratedDocument.id == document_id))
        if document is None:
            return {"status": "error", "message": "document_not_found"}

        pipeline = PipelineService(db)
        exported = pipeline.export_docx(document)
        db.commit()
        return {"status": "ok", "document_id": exported.id, "path": exported.exported_docx_path or ""}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    finally:
        db.close()
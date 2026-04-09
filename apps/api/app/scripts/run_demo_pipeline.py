"""Run fixture-driven end-to-end demo pipeline."""

from __future__ import annotations

from sqlalchemy import select

from app.application.services.pipeline_service import PipelineService
from app.application.services.prompt_registry import PromptRegistry
from app.db.session import SessionLocal
from app.domain.models import Session


def run() -> None:
    db = SessionLocal()
    try:
        session_obj = db.scalar(select(Session).order_by(Session.created_at.desc()).limit(1))
        if session_obj is None:
            raise RuntimeError("No session found. Run seed_demo first.")

        registry = PromptRegistry(db)
        registry.ensure_seeded(["clinical_draft"])

        pipeline = PipelineService(db)
        transcript_id = pipeline.ingest_from_meet(session_obj)
        draft = pipeline.generate_draft(session_obj, regenerate=False)
        document = pipeline.create_document(session_obj, draft)
        exported = pipeline.export_docx(document)

        db.commit()

        print("Demo pipeline completed")
        print(f"Session: {session_obj.id}")
        print(f"Transcript: {transcript_id}")
        print(f"Draft: {draft.id} (version {draft.version})")
        print(f"Google Doc URL: {document.google_doc_url}")
        print(f"DOCX path: {exported.exported_docx_path}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
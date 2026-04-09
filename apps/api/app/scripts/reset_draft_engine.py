"""Reset clinical drafting data from scratch.

Deletes existing drafts/documents/risk flags/jobs and clears exported artifacts so the
next generation run starts from a clean slate using the current active template.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.domain.enums import SessionStatus
from app.domain.models import ClinicalDraft, GeneratedDocument, ProcessingJob, RiskFlag, Session, Therapist

CURRENT_TEMPLATE_DOCX = "plantilla_historia_clinica_respira_integral_editable_final.docx"
CURRENT_TEMPLATE_PDF = "plantilla_historia_clinica_respira_integral_of.pdf"


def _templates_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "templates"


def _artifacts_dir() -> Path:
    # docker-compose mounts ./data/artifacts into /app/data/artifacts
    return Path("/app/data/artifacts")


def run() -> None:
    templates_dir = _templates_dir()
    default_docx = templates_dir / CURRENT_TEMPLATE_DOCX
    default_pdf = templates_dir / CURRENT_TEMPLATE_PDF
    artifacts_dir = _artifacts_dir()

    db = SessionLocal()
    try:
        sessions = db.scalars(select(Session)).all()
        therapists = db.scalars(select(Therapist)).all()
        documents = db.scalars(select(GeneratedDocument)).all()
        drafts = db.scalars(select(ClinicalDraft)).all()
        flags = db.scalars(select(RiskFlag)).all()
        jobs = db.scalars(select(ProcessingJob)).all()

        removed_files = 0
        exports_dir = artifacts_dir / "exports"
        for document in documents:
            for candidate in [document.exported_docx_path, document.exported_pdf_path]:
                if not candidate:
                    continue
                path = Path(candidate)
                if path.exists() and path.is_file():
                    path.unlink(missing_ok=True)
                    removed_files += 1

            if document.google_doc_id:
                payload_path = artifacts_dir / f"{document.google_doc_id}.gdoc.mock.json"
                if payload_path.exists() and payload_path.is_file():
                    payload_path.unlink(missing_ok=True)
                    removed_files += 1

        if exports_dir.exists():
            for file_path in exports_dir.rglob("*"):
                if file_path.is_file():
                    file_path.unlink(missing_ok=True)
                    removed_files += 1

        for payload in artifacts_dir.glob("mock-*.gdoc.mock.json"):
            if payload.is_file():
                payload.unlink(missing_ok=True)
                removed_files += 1

        profiles_dir = artifacts_dir / "profiles"
        if profiles_dir.exists():
            for template_file in profiles_dir.glob("*/template/*"):
                if template_file.is_file():
                    template_file.unlink(missing_ok=True)
                    removed_files += 1

        for therapist in therapists:
            therapist.template_docx_path = str(default_docx) if default_docx.exists() else None
            therapist.template_pdf_path = str(default_pdf) if default_pdf.exists() else None
            db.add(therapist)

        for session in sessions:
            session.status = SessionStatus.processing
            db.add(session)

        for item in jobs:
            db.delete(item)
        for item in flags:
            db.delete(item)
        for item in documents:
            db.delete(item)
        for item in drafts:
            db.delete(item)

        db.commit()

        print("Draft engine reset completed")
        print(f"Sessions updated: {len(sessions)}")
        print(f"Therapists re-linked to current template: {len(therapists)}")
        print(f"Deleted drafts: {len(drafts)}")
        print(f"Deleted documents: {len(documents)}")
        print(f"Deleted risk flags: {len(flags)}")
        print(f"Deleted processing jobs: {len(jobs)}")
        print(f"Deleted cached files: {removed_files}")
        print(f"Default DOCX: {default_docx}")
        print(f"Default PDF: {default_pdf}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()



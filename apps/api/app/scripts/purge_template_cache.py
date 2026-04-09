"""Purge legacy templates and cached generated artifacts.

Use this script when changing to a new clinical template baseline and you need to
force regeneration against the latest format.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.domain.enums import DocumentStatus
from app.domain.models import GeneratedDocument, Therapist

CURRENT_TEMPLATE_DOCX = "plantilla_historia_clinica_respira_integral_editable_final.docx"
CURRENT_TEMPLATE_PDF = "plantilla_historia_clinica_respira_integral_of.pdf"


def _templates_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "templates"


def _cleanup_repo_templates() -> tuple[list[Path], Path, Path]:
    directory = _templates_dir()
    keep = {CURRENT_TEMPLATE_DOCX, CURRENT_TEMPLATE_PDF}
    removed: list[Path] = []

    if directory.exists():
        for candidate in directory.iterdir():
            if not candidate.is_file():
                continue
            if candidate.name in keep:
                continue
            candidate.unlink(missing_ok=True)
            removed.append(candidate)

    return removed, directory / CURRENT_TEMPLATE_DOCX, directory / CURRENT_TEMPLATE_PDF


def _cleanup_artifact_cache(artifacts_dir: Path) -> dict[str, int]:
    removed_exports = 0
    removed_mock_payloads = 0
    removed_profile_templates = 0

    exports_dir = artifacts_dir / "exports"
    if exports_dir.exists():
        for file_path in exports_dir.rglob("*"):
            if file_path.is_file():
                file_path.unlink(missing_ok=True)
                removed_exports += 1

    for payload in artifacts_dir.glob("mock-*.gdoc.mock.json"):
        if payload.is_file():
            payload.unlink(missing_ok=True)
            removed_mock_payloads += 1

    profiles_dir = artifacts_dir / "profiles"
    if profiles_dir.exists():
        for template_file in profiles_dir.glob("*/template/*"):
            if template_file.is_file():
                template_file.unlink(missing_ok=True)
                removed_profile_templates += 1

    return {
        "removed_exports": removed_exports,
        "removed_mock_payloads": removed_mock_payloads,
        "removed_profile_templates": removed_profile_templates,
    }


def _reset_db_references(default_docx: Path, default_pdf: Path) -> dict[str, int]:
    db = SessionLocal()
    try:
        therapists = db.scalars(select(Therapist)).all()
        documents = db.scalars(select(GeneratedDocument)).all()

        updated_therapists = 0
        for therapist in therapists:
            therapist.template_docx_path = str(default_docx) if default_docx.exists() else None
            therapist.template_pdf_path = str(default_pdf) if default_pdf.exists() else None
            db.add(therapist)
            updated_therapists += 1

        reset_documents = 0
        for document in documents:
            had_export_data = bool(document.exported_pdf_path or document.exported_docx_path)
            document.exported_pdf_path = None
            document.exported_pdf_mime_type = None
            document.exported_docx_path = None
            document.exported_docx_mime_type = None
            if document.status == DocumentStatus.exported:
                document.status = DocumentStatus.created
            db.add(document)
            if had_export_data:
                reset_documents += 1

        db.commit()
        return {
            "updated_therapists": updated_therapists,
            "reset_documents": reset_documents,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run() -> None:
    removed_templates, default_docx, default_pdf = _cleanup_repo_templates()
    cache_stats = _cleanup_artifact_cache(Path(settings.artifacts_dir))
    db_stats = _reset_db_references(default_docx=default_docx, default_pdf=default_pdf)

    print("Template/cache cleanup completed")
    print(f"Default DOCX: {default_docx}")
    print(f"Default PDF: {default_pdf}")
    print(f"Removed legacy template files: {len(removed_templates)}")
    print(f"Removed export files: {cache_stats['removed_exports']}")
    print(f"Removed mock payloads: {cache_stats['removed_mock_payloads']}")
    print(f"Removed profile template files: {cache_stats['removed_profile_templates']}")
    print(f"Therapists reset to default template: {db_stats['updated_therapists']}")
    print(f"Documents reset for fresh export: {db_stats['reset_documents']}")


if __name__ == "__main__":
    run()



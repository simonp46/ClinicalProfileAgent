"""Document routes."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.deps import get_current_therapist
from app.application.services.document_service import DocumentGenerationService
from app.db.session import get_db
from app.domain.models import GeneratedDocument, Therapist

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/{document_id}/export-docx")
def export_docx(
    document_id: str,
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict:
    document = _get_document_or_404(db, document_id)

    service = DocumentGenerationService(db)
    exported = service.export_docx(document)
    db.commit()
    db.refresh(exported)
    return {
        "document_id": exported.id,
        "status": exported.status.value,
        "exported_docx_path": exported.exported_docx_path,
        "exported_docx_mime_type": exported.exported_docx_mime_type,
    }


@router.post("/{document_id}/export-pdf")
def export_pdf(
    document_id: str,
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict:
    document = _get_document_or_404(db, document_id)

    service = DocumentGenerationService(db)
    exported = service.export_pdf(document)
    db.commit()
    db.refresh(exported)
    return {
        "document_id": exported.id,
        "status": exported.status.value,
        "exported_pdf_path": exported.exported_pdf_path,
        "exported_pdf_mime_type": exported.exported_pdf_mime_type,
    }


@router.get("/{document_id}/file")
def get_file(
    document_id: str,
    format: Literal["pdf", "docx"] = Query(default="pdf"),
    disposition: Literal["inline", "attachment"] = Query(default="attachment"),
    refresh: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> FileResponse:
    document = _get_document_or_404(db, document_id)
    service = DocumentGenerationService(db)

    if format == "pdf":
        if refresh or not document.exported_pdf_path or not Path(document.exported_pdf_path).exists():
            document = service.export_pdf(document)
            db.commit()
            db.refresh(document)
        file_path = document.exported_pdf_path
        media_type = document.exported_pdf_mime_type or "application/pdf"
        file_name = f"clinical-draft-{document.id}.pdf"
    else:
        if refresh or not document.exported_docx_path or not Path(document.exported_docx_path).exists():
            document = service.export_docx(document)
            db.commit()
            db.refresh(document)
        file_path = document.exported_docx_path
        media_type = (
            document.exported_docx_mime_type
            or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        file_name = f"clinical-draft-{document.id}.docx"

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exported file not found")

    response = FileResponse(path=file_path, media_type=media_type, filename=file_name)
    response.headers["Content-Disposition"] = f'{disposition}; filename="{file_name}"'
    return response



@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    document = _get_document_or_404(db, document_id)

    service = DocumentGenerationService(db)
    service.delete_document(document, actor_id=current_user.id)
    db.commit()

    return {
        "document_id": document_id,
        "status": "deleted",
    }

def _get_document_or_404(db: Session, document_id: str) -> GeneratedDocument:
    document = db.scalar(select(GeneratedDocument).where(GeneratedDocument.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document



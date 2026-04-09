"""Clinical draft routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.deps import get_current_therapist
from app.application.services.clinical_draft_service import ClinicalDraftService
from app.application.services.document_service import DocumentGenerationService
from app.db.session import get_db
from app.domain.models import ClinicalDraft, Session as SessionModel, Therapist
from app.domain.schemas import ReviewDraftRequest

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("/{draft_id}/approve")
def approve_draft(
    draft_id: str,
    payload: ReviewDraftRequest,
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    draft = db.scalar(select(ClinicalDraft).where(ClinicalDraft.id == draft_id))
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    service = ClinicalDraftService(db)
    service.approve_draft(
        draft,
        reviewer_id=current_user.id,
        notes=payload.therapist_review_notes,
        edited_profile_text=payload.clinical_profile_text,
        edited_summary=payload.session_summary,
    )
    db.commit()
    db.refresh(draft)
    return {"draft_id": draft.id, "status": draft.status.value}


@router.post("/{draft_id}/reject")
def reject_draft(
    draft_id: str,
    payload: ReviewDraftRequest,
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    draft = db.scalar(select(ClinicalDraft).where(ClinicalDraft.id == draft_id))
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    service = ClinicalDraftService(db)
    service.reject_draft(
        draft,
        reviewer_id=current_user.id,
        notes=payload.therapist_review_notes,
        edited_profile_text=payload.clinical_profile_text,
        edited_summary=payload.session_summary,
    )
    db.commit()
    db.refresh(draft)
    return {"draft_id": draft.id, "status": draft.status.value}


@router.post("/{draft_id}/create-google-doc")
def create_google_doc(
    draft_id: str,
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict:
    draft = db.scalar(select(ClinicalDraft).where(ClinicalDraft.id == draft_id))
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    session = db.scalar(select(SessionModel).where(SessionModel.id == draft.session_id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    service = DocumentGenerationService(db)
    generated = service.create_document(session, draft)
    db.commit()
    db.refresh(generated)
    return {
        "document_id": generated.id,
        "google_doc_id": generated.google_doc_id,
        "google_doc_url": generated.google_doc_url,
        "status": generated.status.value,
    }

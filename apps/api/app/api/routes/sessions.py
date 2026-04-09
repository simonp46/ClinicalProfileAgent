"""Session routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.routes.deps import get_current_therapist
from app.application.services.google_session_sync_service import (
    GoogleSessionSyncError,
    GoogleSessionSyncService,
)
from app.application.services.pipeline_service import PipelineService
from app.application.services.session_service import SessionService
from app.db.session import get_db
from app.domain.models import Patient, Therapist, Transcript
from app.domain.models import Session as SessionModel
from app.domain.schemas import PatientUpdate, SessionCreate
from app.infrastructure.adapters.google_calendar_adapter import (
    CalendarAdapterError,
    MockCalendarAdapter,
    build_calendar_adapter,
)
from app.worker.tasks import generate_draft_task, process_session_task, regenerate_draft_task

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict:
    service = SessionService(db)
    session = service.create_session(payload)
    db.commit()
    db.refresh(session)
    return {"session": _serialize_session(session)}


@router.get("")
def list_sessions(
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    service = SessionService(db)
    sessions = service.list_sessions(therapist_id=current_user.id)
    return {"items": [_serialize_session(item) for item in sessions]}


@router.get("/upcoming-meetings")
def list_upcoming_meetings(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    items = _list_upcoming_meetings(db=db, therapist=current_user, limit=limit)
    return {"items": items}


@router.post("/sync-google")
def sync_google_sessions(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    service = GoogleSessionSyncService(db)
    try:
        result = service.sync_for_therapist(current_user, limit=limit)
    except GoogleSessionSyncError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    return {"status": "ok", **result.as_dict()}


@router.get("/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict:
    service = SessionService(db)
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"session": _serialize_session_detail(session)}


@router.patch("/{session_id}/patient")
def update_session_patient(
    session_id: str,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    service = SessionService(db)
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        patient = service.update_patient(session=session, payload=payload, actor_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    db.refresh(patient)
    return {"patient": _serialize_patient(patient)}


@router.get("/{session_id}/transcript")
def get_transcript(
    session_id: str,
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict:
    transcript = db.scalar(select(Transcript).where(Transcript.session_id == session_id))
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found")

    segments = [
        {
            "id": item.id,
            "speaker_label": item.speaker_label,
            "original_participant_ref": item.original_participant_ref,
            "text": item.text,
            "start_time": item.start_time.isoformat() if item.start_time else None,
            "end_time": item.end_time.isoformat() if item.end_time else None,
            "sequence_no": item.sequence_no,
        }
        for item in transcript.segments
    ]

    return {
        "id": transcript.id,
        "raw_text": transcript.raw_text,
        "normalized_text": transcript.normalized_text,
        "deidentified_text": transcript.deidentified_text,
        "language_code": transcript.language_code,
        "google_docs_uri": transcript.google_docs_uri,
        "segments": sorted(segments, key=lambda x: x["sequence_no"]),
    }


@router.post("/{session_id}/process")
def process_session(
    session_id: str,
    sync: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict[str, str]:
    session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if sync:
        pipeline = PipelineService(db)
        pipeline.ingest_from_meet(session)
        db.commit()
        return {"status": "processed"}

    process_session_task.delay(session_id)
    db.commit()
    return {"status": "queued"}


@router.post("/{session_id}/generate-draft")
def generate_draft(
    session_id: str,
    sync: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict[str, str]:
    session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if sync:
        pipeline = PipelineService(db)
        draft = pipeline.generate_draft(session, regenerate=False)
        db.commit()
        return {"status": "generated", "draft_id": draft.id}

    generate_draft_task.delay(session_id)
    db.commit()
    return {"status": "queued"}


@router.post("/{session_id}/regenerate-draft")
def regenerate_draft(
    session_id: str,
    sync: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict[str, str]:
    session = db.scalar(select(SessionModel).where(SessionModel.id == session_id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if sync:
        pipeline = PipelineService(db)
        draft = pipeline.generate_draft(session, regenerate=True)
        db.commit()
        return {"status": "generated", "draft_id": draft.id}

    regenerate_draft_task.delay(session_id)
    db.commit()
    return {"status": "queued"}


def _list_upcoming_meetings(*, db: Session, therapist: Therapist, limit: int) -> list[dict]:
    try:
        adapter = build_calendar_adapter(
            db=db,
            therapist_id=therapist.id,
            therapist=therapist,
            impersonated_user=therapist.google_account_email,
        )
        items = adapter.list_upcoming_meetings(limit=limit)
    except CalendarAdapterError:
        items = MockCalendarAdapter(db=db, therapist_id=therapist.id).list_upcoming_meetings(
            limit=limit
        )

    event_ids = [str(item.get("event_id")) for item in items if item.get("event_id")]
    if not event_ids:
        return items

    linked_sessions = db.scalars(
        select(SessionModel)
        .where(
            SessionModel.therapist_id == therapist.id,
            SessionModel.calendar_event_id.in_(event_ids),
        )
        .options(joinedload(SessionModel.patient))
    ).all()
    linked_by_event_id = {
        session.calendar_event_id: session
        for session in linked_sessions
        if session.calendar_event_id
    }

    for item in items:
        linked = linked_by_event_id.get(str(item.get("event_id") or ""))
        if linked is None:
            continue
        item["linked_session_id"] = linked.id
        if linked.patient:
            full_name = f"{linked.patient.first_name} {linked.patient.last_name}".strip()
            item["linked_patient_name"] = full_name or None
    return items


def _serialize_patient(patient: Patient) -> dict:
    return {
        "id": patient.id,
        "external_patient_id": patient.external_patient_id,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
        "age": patient.age,
        "gender": patient.gender,
        "phone": patient.phone,
        "email": patient.email,
        "address": patient.address,
        "city": patient.city,
        "profession": patient.profession,
        "notes": patient.notes,
        "consent_reference": patient.consent_reference,
        "intake_id": patient.intake_id,
        "signed_form_id": patient.signed_form_id,
    }


def _serialize_session(session: SessionModel) -> dict:
    return {
        "id": session.id,
        "therapist_id": session.therapist_id,
        "patient_id": session.patient_id,
        "status": session.status.value,
        "source": session.source.value,
        "google_meet_space_name": session.google_meet_space_name,
        "google_conference_record_name": session.google_conference_record_name,
        "calendar_event_id": session.calendar_event_id,
        "session_started_at": (
            session.session_started_at.isoformat() if session.session_started_at else None
        ),
        "session_ended_at": (
            session.session_ended_at.isoformat() if session.session_ended_at else None
        ),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "patient": _serialize_patient(session.patient) if session.patient else None,
        "therapist": (
            {
                "id": session.therapist.id,
                "full_name": session.therapist.full_name,
                "email": session.therapist.email,
            }
            if session.therapist
            else None
        ),
    }


def _serialize_session_detail(session: SessionModel) -> dict:
    payload = _serialize_session(session)
    payload["drafts"] = [
        {
            "id": draft.id,
            "version": draft.version,
            "status": draft.status.value,
            "llm_model": draft.llm_model,
            "prompt_version": draft.prompt_version,
            "session_summary": draft.session_summary,
            "clinical_profile_text": draft.clinical_profile_text,
            "structured_json": draft.structured_json,
            "therapist_review_notes": draft.therapist_review_notes,
            "created_at": draft.created_at.isoformat(),
            "updated_at": draft.updated_at.isoformat(),
        }
        for draft in sorted(
            session.drafts, key=lambda item: (item.version, item.created_at), reverse=True
        )
    ]
    payload["risk_flags"] = [
        {
            "id": flag.id,
            "severity": flag.severity.value,
            "category": flag.category.value,
            "snippet": flag.snippet,
            "rationale": flag.rationale,
            "requires_human_review": flag.requires_human_review,
            "created_at": flag.created_at.isoformat(),
        }
        for flag in session.risk_flags
    ]
    payload["documents"] = [
        {
            "id": doc.id,
            "clinical_draft_id": doc.clinical_draft_id,
            "google_doc_id": doc.google_doc_id,
            "google_doc_url": doc.google_doc_url,
            "exported_docx_path": doc.exported_docx_path,
            "exported_docx_mime_type": doc.exported_docx_mime_type,
            "exported_pdf_path": doc.exported_pdf_path,
            "exported_pdf_mime_type": doc.exported_pdf_mime_type,
            "status": doc.status.value,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        }
        for doc in sorted(session.documents, key=lambda item: item.created_at, reverse=True)
    ]
    payload["processing_jobs"] = [
        {
            "id": job.id,
            "job_type": job.job_type.value,
            "status": job.status.value,
            "attempts": job.attempts,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
        for job in session.processing_jobs
    ]
    return payload

"""Google Workspace events webhook routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.models import Session as SessionModel
from app.domain.schemas import WorkspaceEventPayload
from app.infrastructure.adapters.workspace_events_adapter import WorkspaceEventsAdapter
from app.worker.tasks import process_and_generate_task

router = APIRouter(prefix="/webhooks/google", tags=["webhooks"])


@router.post("/workspace-events")
async def receive_workspace_event(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    body = await request.body()
    adapter = WorkspaceEventsAdapter()
    signature = request.headers.get(adapter.HEADER_SIGNATURE)

    if not adapter.validate_signature(body=body, signature_header=signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    payload = WorkspaceEventPayload.model_validate_json(body)

    session = _resolve_session(db, payload)
    if session is None:
        return {"status": "ignored", "reason": "session_not_found"}

    process_and_generate_task.delay(session.id, payload.transcript_name)
    return {"status": "accepted", "session_id": session.id}


def _resolve_session(db: Session, payload: WorkspaceEventPayload) -> SessionModel | None:
    if payload.session_id:
        by_id = db.scalar(select(SessionModel).where(SessionModel.id == payload.session_id))
        if by_id:
            return by_id

    if payload.conference_record_name:
        by_conference = db.scalar(
            select(SessionModel).where(
                SessionModel.google_conference_record_name == payload.conference_record_name
            )
        )
        if by_conference:
            return by_conference

    if payload.transcript_name:
        by_transcript = db.scalar(
            select(SessionModel).where(SessionModel.google_meet_space_name == payload.transcript_name)
        )
        if by_transcript:
            return by_transcript

    return None
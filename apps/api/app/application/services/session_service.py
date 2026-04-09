"""Session domain service."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.application.services.audit_service import AuditService
from app.domain.enums import AuditActorType, ClinicalDraftStatus, SessionStatus
from app.domain.models import ClinicalDraft, Patient, Session as SessionModel
from app.domain.schemas import PatientCreate, PatientUpdate, SessionCreate

_ALLOWED_SESSION_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.scheduled: {SessionStatus.processing, SessionStatus.failed},
    SessionStatus.processing: {SessionStatus.ready_for_review, SessionStatus.failed},
    SessionStatus.ready_for_review: {SessionStatus.approved, SessionStatus.processing, SessionStatus.failed},
    SessionStatus.approved: {SessionStatus.processing},
    SessionStatus.failed: {SessionStatus.processing},
}


class SessionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit = AuditService(db)

    def create_session(self, payload: SessionCreate) -> SessionModel:
        patient = self._create_patient(payload.patient)
        session = SessionModel(
            therapist_id=payload.therapist_id,
            patient_id=patient.id,
            google_meet_space_name=payload.google_meet_space_name,
            google_conference_record_name=payload.google_conference_record_name,
            calendar_event_id=payload.calendar_event_id,
            session_started_at=payload.session_started_at,
            session_ended_at=payload.session_ended_at,
            source=payload.source,
            status=SessionStatus.scheduled,
        )
        self.db.add(session)
        self.db.flush()

        self.audit.log(
            actor_type=AuditActorType.system,
            entity_type="session",
            entity_id=session.id,
            action="session.created",
            metadata={"therapist_id": payload.therapist_id, "patient_id": patient.id},
        )
        return session

    def list_sessions(self, therapist_id: str | None = None) -> list[SessionModel]:
        query: Select[tuple[SessionModel]] = (
            select(SessionModel)
            .options(joinedload(SessionModel.patient), joinedload(SessionModel.therapist))
            .order_by(SessionModel.created_at.desc())
        )
        if therapist_id:
            query = query.where(SessionModel.therapist_id == therapist_id)
        return list(self.db.scalars(query).unique().all())

    def get_session(self, session_id: str) -> SessionModel | None:
        query = (
            select(SessionModel)
            .where(SessionModel.id == session_id)
            .options(
                joinedload(SessionModel.patient),
                joinedload(SessionModel.therapist),
                joinedload(SessionModel.transcript),
                joinedload(SessionModel.drafts),
                joinedload(SessionModel.risk_flags),
                joinedload(SessionModel.documents),
                joinedload(SessionModel.processing_jobs),
            )
        )
        return self.db.scalar(query)

    def update_status(self, session: SessionModel, new_status: SessionStatus) -> SessionModel:
        allowed = _ALLOWED_SESSION_TRANSITIONS.get(session.status, set())
        if new_status not in allowed and new_status != session.status:
            raise ValueError(f"Invalid session status transition {session.status} -> {new_status}")
        session.status = new_status
        self.db.add(session)
        self.audit.log(
            actor_type=AuditActorType.system,
            entity_type="session",
            entity_id=session.id,
            action="session.status_updated",
            metadata={"status": new_status.value},
        )
        return session

    def update_patient(
        self,
        *,
        session: SessionModel,
        payload: PatientUpdate,
        actor_id: str | None = None,
    ) -> Patient:
        patient = session.patient
        if patient is None:
            patient = self.db.scalar(select(Patient).where(Patient.id == session.patient_id))

        if patient is None:
            raise ValueError("Patient not found for session")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return patient

        full_name = updates.pop("full_name", None)
        if isinstance(full_name, str):
            first_name, last_name = self._split_full_name(full_name, current_last_name=patient.last_name)
            updates["first_name"] = first_name
            updates["last_name"] = last_name

        if "email" in updates and updates["email"] is not None:
            updates["email"] = str(updates["email"])

        for field, value in updates.items():
            if field in {"first_name", "last_name"} and (value is None or str(value).strip() == ""):
                continue
            setattr(patient, field, value)

        self.db.add(patient)
        self.audit.log(
            actor_type=AuditActorType.therapist,
            actor_id=actor_id,
            entity_type="patient",
            entity_id=patient.id,
            action="patient.updated",
            metadata={
                "session_id": session.id,
                "updated_fields": sorted(list(updates.keys())),
            },
        )
        return patient

    def next_draft_version(self, session_id: str) -> int:
        latest = self.db.scalar(
            select(ClinicalDraft)
            .where(ClinicalDraft.session_id == session_id)
            .order_by(ClinicalDraft.version.desc())
            .limit(1)
        )
        return (latest.version + 1) if latest else 1

    def supersede_existing_drafts(self, session_id: str) -> None:
        drafts = self.db.scalars(
            select(ClinicalDraft).where(
                ClinicalDraft.session_id == session_id,
                ClinicalDraft.status.in_([ClinicalDraftStatus.generated, ClinicalDraftStatus.reviewed]),
            )
        ).all()
        for draft in drafts:
            draft.status = ClinicalDraftStatus.superseded
            self.db.add(draft)

    def _create_patient(self, payload: PatientCreate) -> Patient:
        patient = Patient(
            external_patient_id=payload.external_patient_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            birth_date=payload.birth_date,
            age=payload.age,
            gender=payload.gender,
            phone=payload.phone,
            email=str(payload.email) if payload.email else None,
            address=payload.address,
            city=payload.city,
            profession=payload.profession,
            notes=payload.notes,
            consent_reference=payload.consent_reference,
            intake_id=payload.intake_id,
            signed_form_id=payload.signed_form_id,
        )
        self.db.add(patient)
        self.db.flush()
        return patient

    def _split_full_name(self, full_name: str, *, current_last_name: str | None = None) -> tuple[str, str]:
        cleaned = " ".join(full_name.split())
        if not cleaned:
            return "Paciente", current_last_name or "No especificado"

        parts = cleaned.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else (current_last_name or "No especificado")
        return first_name, last_name




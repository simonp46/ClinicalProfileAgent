"""SQLAlchemy domain models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import EncryptedString
from app.domain.enums import (
    AuditActorType,
    ClinicalDraftStatus,
    DocumentStatus,
    ProcessingJobStatus,
    ProcessingJobType,
    RiskCategory,
    RiskSeverity,
    SessionSource,
    SessionStatus,
    UserRole,
)


def _uuid_str() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Therapist(Base, TimestampMixin):
    __tablename__ = "therapists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    google_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_oauth_subject: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    google_oauth_access_token: Mapped[str | None] = mapped_column(
        EncryptedString(4096), nullable=True
    )
    google_oauth_refresh_token: Mapped[str | None] = mapped_column(
        EncryptedString(4096), nullable=True
    )
    google_oauth_scopes: Mapped[str | None] = mapped_column(EncryptedString(2048), nullable=True)
    google_oauth_token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    google_oauth_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    microsoft_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    microsoft_oauth_subject: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    microsoft_oauth_access_token: Mapped[str | None] = mapped_column(
        EncryptedString(4096), nullable=True
    )
    microsoft_oauth_refresh_token: Mapped[str | None] = mapped_column(
        EncryptedString(4096), nullable=True
    )
    microsoft_oauth_scopes: Mapped[str | None] = mapped_column(EncryptedString(2048), nullable=True)
    microsoft_oauth_token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    microsoft_oauth_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(EncryptedString(128), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    address: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    city: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    profession: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    profile_photo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    signature_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    template_pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    template_docx_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.therapist, nullable=False
    )

    sessions: Mapped[list[Session]] = relationship("Session", back_populates="therapist")


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    external_patient_id: Mapped[str | None] = mapped_column(String(128), index=True)
    first_name: Mapped[str] = mapped_column(EncryptedString(255), nullable=False)
    last_name: Mapped[str] = mapped_column(EncryptedString(255), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString(128), nullable=True)
    email: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    address: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    city: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    profession: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(EncryptedString(4000), nullable=True)
    consent_reference: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    intake_id: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    signed_form_id: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)

    sessions: Mapped[list[Session]] = relationship("Session", back_populates="patient")


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    therapist_id: Mapped[str] = mapped_column(
        ForeignKey("therapists.id", ondelete="CASCADE"), index=True
    )
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    google_meet_space_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_conference_record_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calendar_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.scheduled, nullable=False, index=True
    )
    source: Mapped[SessionSource] = mapped_column(
        Enum(SessionSource), default=SessionSource.google_meet, nullable=False
    )

    therapist: Mapped[Therapist] = relationship("Therapist", back_populates="sessions")
    patient: Mapped[Patient] = relationship("Patient", back_populates="sessions")
    transcript: Mapped[Transcript | None] = relationship(
        "Transcript", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    drafts: Mapped[list[ClinicalDraft]] = relationship(
        "ClinicalDraft", back_populates="session", cascade="all, delete-orphan"
    )
    documents: Mapped[list[GeneratedDocument]] = relationship(
        "GeneratedDocument", back_populates="session", cascade="all, delete-orphan"
    )
    risk_flags: Mapped[list[RiskFlag]] = relationship(
        "RiskFlag", back_populates="session", cascade="all, delete-orphan"
    )
    processing_jobs: Mapped[list[ProcessingJob]] = relationship(
        "ProcessingJob", back_populates="session", cascade="all, delete-orphan"
    )


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    google_transcript_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_docs_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    deidentified_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    session: Mapped[Session] = relationship("Session", back_populates="transcript")
    segments: Mapped[list[TranscriptSegment]] = relationship(
        "TranscriptSegment", back_populates="transcript", cascade="all, delete-orphan"
    )
    mappings: Mapped[list[DeidentificationMap]] = relationship(
        "DeidentificationMap", back_populates="transcript", cascade="all, delete-orphan"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (UniqueConstraint("transcript_id", "sequence_no", name="uq_segment_sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    transcript_id: Mapped[str] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    speaker_label: Mapped[str] = mapped_column(String(64), nullable=False)
    original_participant_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transcript: Mapped[Transcript] = relationship("Transcript", back_populates="segments")


class ClinicalDraft(Base, TimestampMixin):
    __tablename__ = "clinical_drafts"
    __table_args__ = (UniqueConstraint("session_id", "version", name="uq_draft_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ClinicalDraftStatus] = mapped_column(
        Enum(ClinicalDraftStatus), default=ClinicalDraftStatus.generated, index=True
    )
    structured_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    session_summary: Mapped[str] = mapped_column(Text, nullable=False)
    clinical_profile_text: Mapped[str] = mapped_column(Text, nullable=False)
    therapist_review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[Session] = relationship("Session", back_populates="drafts")
    documents: Mapped[list[GeneratedDocument]] = relationship(
        "GeneratedDocument", back_populates="clinical_draft", cascade="all, delete-orphan"
    )


class GeneratedDocument(Base, TimestampMixin):
    __tablename__ = "generated_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    clinical_draft_id: Mapped[str] = mapped_column(
        ForeignKey("clinical_drafts.id", ondelete="CASCADE"), index=True
    )
    google_doc_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_doc_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    exported_docx_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    exported_docx_mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exported_pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    exported_pdf_mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.created, nullable=False
    )

    session: Mapped[Session] = relationship("Session", back_populates="documents")
    clinical_draft: Mapped[ClinicalDraft] = relationship(
        "ClinicalDraft", back_populates="documents"
    )


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[RiskSeverity] = mapped_column(Enum(RiskSeverity), nullable=False)
    category: Mapped[RiskCategory] = mapped_column(Enum(RiskCategory), nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[Session] = relationship("Session", back_populates="risk_flags")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    actor_type: Mapped[AuditActorType] = mapped_column(Enum(AuditActorType), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[ProcessingJobType] = mapped_column(Enum(ProcessingJobType), nullable=False)
    status: Mapped[ProcessingJobStatus] = mapped_column(
        Enum(ProcessingJobStatus), default=ProcessingJobStatus.pending, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    session: Mapped[Session] = relationship("Session", back_populates="processing_jobs")


class DeidentificationMap(Base):
    __tablename__ = "deidentification_maps"
    __table_args__ = (UniqueConstraint("transcript_id", "placeholder", name="uq_deid_placeholder"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    transcript_id: Mapped[str] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    placeholder: Mapped[str] = mapped_column(String(128), nullable=False)
    original_value: Mapped[str] = mapped_column(EncryptedString(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transcript: Mapped[Transcript] = relationship("Transcript", back_populates="mappings")


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_prompt_name_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthRefreshToken(Base, TimestampMixin):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    therapist_id: Mapped[str] = mapped_column(
        ForeignKey("therapists.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    therapist: Mapped[Therapist] = relationship("Therapist")

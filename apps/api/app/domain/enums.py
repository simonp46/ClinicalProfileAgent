"""Domain enums."""

from __future__ import annotations

from enum import Enum


class SessionStatus(str, Enum):
    scheduled = "scheduled"
    processing = "processing"
    ready_for_review = "ready_for_review"
    approved = "approved"
    failed = "failed"


class SessionSource(str, Enum):
    google_meet = "google_meet"
    microsoft_teams = "microsoft_teams"


class ClinicalDraftStatus(str, Enum):
    generated = "generated"
    reviewed = "reviewed"
    approved = "approved"
    superseded = "superseded"


class DocumentStatus(str, Enum):
    created = "created"
    exported = "exported"
    failed = "failed"


class RiskSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskCategory(str, Enum):
    self_harm = "self_harm"
    suicide_risk = "suicide_risk"
    violence = "violence"
    abuse = "abuse"
    dissociation = "dissociation"
    psychosis = "psychosis"
    substance_use = "substance_use"
    safeguarding = "safeguarding"
    other = "other"


class AuditActorType(str, Enum):
    system = "system"
    therapist = "therapist"


class ProcessingJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class ProcessingJobType(str, Enum):
    ingest_transcript = "ingest_transcript"
    generate_draft = "generate_draft"
    create_doc = "create_doc"
    export_docx = "export_docx"


class UserRole(str, Enum):
    therapist = "therapist"
    admin = "admin"

"""Initial schema for therapy-meet-copilot.

Revision ID: 20260325_0001
Revises:
Create Date: 2026-03-25 10:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "20260325_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_role_enum = postgresql.ENUM("therapist", "admin", name="userrole", create_type=False)
    session_status_enum = postgresql.ENUM(
        "scheduled",
        "processing",
        "ready_for_review",
        "approved",
        "failed",
        name="sessionstatus",
        create_type=False,
    )
    session_source_enum = postgresql.ENUM("google_meet", name="sessionsource", create_type=False)
    clinical_status_enum = postgresql.ENUM(
        "generated",
        "reviewed",
        "approved",
        "superseded",
        name="clinicaldraftstatus",
        create_type=False,
    )
    document_status_enum = postgresql.ENUM(
        "created", "exported", "failed", name="documentstatus", create_type=False
    )
    risk_severity_enum = postgresql.ENUM(
        "low", "medium", "high", "critical", name="riskseverity", create_type=False
    )
    risk_category_enum = postgresql.ENUM(
        "self_harm",
        "suicide_risk",
        "violence",
        "abuse",
        "dissociation",
        "psychosis",
        "substance_use",
        "safeguarding",
        "other",
        name="riskcategory",
        create_type=False,
    )
    audit_actor_type_enum = postgresql.ENUM(
        "system", "therapist", name="auditactortype", create_type=False
    )
    processing_job_status_enum = postgresql.ENUM(
        "pending", "running", "success", "failed", name="processingjobstatus", create_type=False
    )
    processing_job_type_enum = postgresql.ENUM(
        "ingest_transcript",
        "generate_draft",
        "create_doc",
        "export_docx",
        name="processingjobtype",
        create_type=False,
    )

    bind = op.get_bind()
    user_role_enum.create(bind, checkfirst=True)
    session_status_enum.create(bind, checkfirst=True)
    session_source_enum.create(bind, checkfirst=True)
    clinical_status_enum.create(bind, checkfirst=True)
    document_status_enum.create(bind, checkfirst=True)
    risk_severity_enum.create(bind, checkfirst=True)
    risk_category_enum.create(bind, checkfirst=True)
    audit_actor_type_enum.create(bind, checkfirst=True)
    processing_job_status_enum.create(bind, checkfirst=True)
    processing_job_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "therapists",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("google_account_email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role_enum, nullable=False, server_default="therapist"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_therapists_email"),
    )

    op.create_table(
        "patients",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("external_patient_id", sa.String(length=128), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("consent_reference", sa.String(length=255), nullable=True),
        sa.Column("intake_id", sa.String(length=255), nullable=True),
        sa.Column("signed_form_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("therapist_id", sa.String(length=36), sa.ForeignKey("therapists.id", ondelete="CASCADE")),
        sa.Column("patient_id", sa.String(length=36), sa.ForeignKey("patients.id", ondelete="CASCADE")),
        sa.Column("google_meet_space_name", sa.String(length=255), nullable=True),
        sa.Column("google_conference_record_name", sa.String(length=255), nullable=True),
        sa.Column("calendar_event_id", sa.String(length=255), nullable=True),
        sa.Column("session_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", session_status_enum, nullable=False, server_default="scheduled"),
        sa.Column("source", session_source_enum, nullable=False, server_default="google_meet"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("google_transcript_name", sa.String(length=255), nullable=True),
        sa.Column("google_docs_uri", sa.String(length=1024), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("deidentified_text", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "transcript_id",
            sa.String(length=36),
            sa.ForeignKey("transcripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("speaker_label", sa.String(length=64), nullable=False),
        sa.Column("original_participant_ref", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("transcript_id", "sequence_no", name="uq_segment_sequence"),
    )

    op.create_table(
        "clinical_drafts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("llm_model", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("status", clinical_status_enum, nullable=False, server_default="generated"),
        sa.Column("structured_json", sa.JSON(), nullable=False),
        sa.Column("session_summary", sa.Text(), nullable=False),
        sa.Column("clinical_profile_text", sa.Text(), nullable=False),
        sa.Column("therapist_review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "version", name="uq_draft_version"),
    )

    op.create_table(
        "generated_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "clinical_draft_id",
            sa.String(length=36),
            sa.ForeignKey("clinical_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("google_doc_id", sa.String(length=255), nullable=True),
        sa.Column("google_doc_url", sa.String(length=1024), nullable=True),
        sa.Column("exported_docx_path", sa.String(length=1024), nullable=True),
        sa.Column("exported_docx_mime_type", sa.String(length=128), nullable=True),
        sa.Column("status", document_status_enum, nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "risk_flags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", risk_severity_enum, nullable=False),
        sa.Column("category", risk_category_enum, nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_type", audit_actor_type_enum, nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_type", processing_job_type_enum, nullable=False),
        sa.Column("status", processing_job_status_enum, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "deidentification_maps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "transcript_id",
            sa.String(length=36),
            sa.ForeignKey("transcripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("placeholder", sa.String(length=128), nullable=False),
        sa.Column("original_value", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("transcript_id", "placeholder", name="uq_deid_placeholder"),
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )

    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "therapist_id",
            sa.String(length=36),
            sa.ForeignKey("therapists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
    )

    op.create_index("ix_patients_external_patient_id", "patients", ["external_patient_id"])
    op.create_index("ix_sessions_therapist_id", "sessions", ["therapist_id"])
    op.create_index("ix_sessions_patient_id", "sessions", ["patient_id"])
    op.create_index("ix_sessions_status", "sessions", ["status"])
    op.create_index("ix_transcripts_source_hash", "transcripts", ["source_hash"])
    op.create_index("ix_transcript_segments_transcript_id", "transcript_segments", ["transcript_id"])
    op.create_index("ix_clinical_drafts_session_id", "clinical_drafts", ["session_id"])
    op.create_index("ix_generated_documents_session_id", "generated_documents", ["session_id"])
    op.create_index("ix_generated_documents_clinical_draft_id", "generated_documents", ["clinical_draft_id"])
    op.create_index("ix_risk_flags_session_id", "risk_flags", ["session_id"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_processing_jobs_session_id", "processing_jobs", ["session_id"])
    op.create_index("ix_deidentification_maps_transcript_id", "deidentification_maps", ["transcript_id"])
    op.create_index("ix_auth_refresh_tokens_therapist_id", "auth_refresh_tokens", ["therapist_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_refresh_tokens_therapist_id", table_name="auth_refresh_tokens")
    op.drop_index("ix_deidentification_maps_transcript_id", table_name="deidentification_maps")
    op.drop_index("ix_processing_jobs_session_id", table_name="processing_jobs")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_risk_flags_session_id", table_name="risk_flags")
    op.drop_index("ix_generated_documents_clinical_draft_id", table_name="generated_documents")
    op.drop_index("ix_generated_documents_session_id", table_name="generated_documents")
    op.drop_index("ix_clinical_drafts_session_id", table_name="clinical_drafts")
    op.drop_index("ix_transcript_segments_transcript_id", table_name="transcript_segments")
    op.drop_index("ix_transcripts_source_hash", table_name="transcripts")
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_patient_id", table_name="sessions")
    op.drop_index("ix_sessions_therapist_id", table_name="sessions")
    op.drop_index("ix_patients_external_patient_id", table_name="patients")

    op.drop_table("auth_refresh_tokens")
    op.drop_table("prompt_templates")
    op.drop_table("deidentification_maps")
    op.drop_table("processing_jobs")
    op.drop_table("audit_logs")
    op.drop_table("risk_flags")
    op.drop_table("generated_documents")
    op.drop_table("clinical_drafts")
    op.drop_table("transcript_segments")
    op.drop_table("transcripts")
    op.drop_table("sessions")
    op.drop_table("patients")
    op.drop_table("therapists")

    bind = op.get_bind()
    sa.Enum("pending", "running", "success", "failed", name="processingjobstatus").drop(bind, checkfirst=True)
    sa.Enum(
        "ingest_transcript", "generate_draft", "create_doc", "export_docx", name="processingjobtype"
    ).drop(bind, checkfirst=True)
    sa.Enum("system", "therapist", name="auditactortype").drop(bind, checkfirst=True)
    sa.Enum(
        "self_harm",
        "suicide_risk",
        "violence",
        "abuse",
        "dissociation",
        "psychosis",
        "substance_use",
        "safeguarding",
        "other",
        name="riskcategory",
    ).drop(bind, checkfirst=True)
    sa.Enum("low", "medium", "high", "critical", name="riskseverity").drop(bind, checkfirst=True)
    sa.Enum("created", "exported", "failed", name="documentstatus").drop(bind, checkfirst=True)
    sa.Enum("generated", "reviewed", "approved", "superseded", name="clinicaldraftstatus").drop(
        bind, checkfirst=True
    )
    sa.Enum("google_meet", name="sessionsource").drop(bind, checkfirst=True)
    sa.Enum("scheduled", "processing", "ready_for_review", "approved", "failed", name="sessionstatus").drop(
        bind, checkfirst=True
    )
    sa.Enum("therapist", "admin", name="userrole").drop(bind, checkfirst=True)
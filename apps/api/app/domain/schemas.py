"""Pydantic schemas used by API and services."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.domain.enums import (
    AuditActorType,
    ClinicalDraftStatus,
    DocumentStatus,
    RiskCategory,
    RiskSeverity,
    SessionSource,
    SessionStatus,
    UserRole,
)


class TokenPair(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    csrf_token: str


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthRegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    google_account_email: EmailStr | None = None


class AuthRefreshRequest(BaseModel):
    csrf_token: str


class TherapistBase(BaseModel):
    full_name: str
    email: EmailStr
    google_account_email: EmailStr | None = None


class TherapistOut(TherapistBase):
    id: str
    role: UserRole

    class Config:
        from_attributes = True


class TherapistProfileUpdate(BaseModel):
    full_name: str | None = None
    google_account_email: EmailStr | None = None
    phone: str | None = None
    contact_email: EmailStr | None = None
    address: str | None = None
    profession: str | None = None


class TherapistProfileOut(BaseModel):
    id: str
    full_name: str
    email: str
    role: UserRole
    google_account_email: str | None
    google_oauth_connected: bool = False
    google_oauth_email: str | None = None
    microsoft_account_email: str | None = None
    microsoft_oauth_connected: bool = False
    microsoft_oauth_email: str | None = None
    phone: str | None
    contact_email: str | None
    address: str | None
    profession: str | None
    profile_photo_path: str | None
    signature_image_path: str | None
    template_pdf_path: str | None
    template_docx_path: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GoogleConnectUrlOut(BaseModel):
    authorization_url: str


class GoogleOAuthCallbackResult(BaseModel):
    connected_email: str | None = None
    granted_scopes: list[str] = Field(default_factory=list)


class PatientCreate(BaseModel):
    external_patient_id: str | None = None
    first_name: str
    last_name: str
    birth_date: date | None = None
    age: int | None = None
    gender: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    city: str | None = None
    profession: str | None = None
    notes: str | None = None
    consent_reference: str | None = None
    intake_id: str | None = None
    signed_form_id: str | None = None


class PatientOut(BaseModel):
    id: str
    external_patient_id: str | None
    first_name: str
    last_name: str
    birth_date: date | None
    age: int | None
    gender: str | None
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    profession: str | None
    notes: str | None
    consent_reference: str | None
    intake_id: str | None
    signed_form_id: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatientUpdate(BaseModel):
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    external_patient_id: str | None = None
    birth_date: date | None = None
    age: int | None = None
    gender: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    city: str | None = None
    profession: str | None = None


class SessionCreate(BaseModel):
    therapist_id: str
    patient: PatientCreate
    google_meet_space_name: str | None = None
    google_conference_record_name: str | None = None
    calendar_event_id: str | None = None
    session_started_at: datetime | None = None
    session_ended_at: datetime | None = None
    source: SessionSource = SessionSource.google_meet


class SessionUpdateStatus(BaseModel):
    status: SessionStatus


class SessionOut(BaseModel):
    id: str
    therapist_id: str
    patient_id: str
    status: SessionStatus
    source: SessionSource
    google_meet_space_name: str | None
    google_conference_record_name: str | None
    calendar_event_id: str | None
    session_started_at: datetime | None
    session_ended_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TranscriptSegmentIn(BaseModel):
    speaker_label: str
    original_participant_ref: str | None = None
    text: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    sequence_no: int


class TranscriptIngestRequest(BaseModel):
    google_transcript_name: str | None = None
    google_docs_uri: str | None = None
    language_code: str | None = "es"
    segments: list[TranscriptSegmentIn]


class TranscriptOut(BaseModel):
    id: str
    session_id: str
    raw_text: str
    normalized_text: str
    deidentified_text: str
    language_code: str | None
    source_hash: str

    class Config:
        from_attributes = True


class ClinicalMetadata(BaseModel):
    requires_human_review: bool = True
    confidence_overall: Literal["low", "medium", "high"]


class RespiratoryPatientPersonalData(BaseModel):
    nombre_paciente: str = "No referido"
    telefono: str = "No referido"
    identificacion: str = "No referido"
    fecha_nacimiento: str = "No referido"
    direccion: str = "No referido"
    ciudad: str = "No referido"
    profesion: str = "No referido"
    email: str = "No referido"


class RespiratoryIdentificationData(BaseModel):
    nombre_paciente: str = "No referido"
    edad: str = "No referido"
    sexo: str = "No referido"
    fecha_consulta: str = "No referido"
    motivo_consulta: str = "No referido"


class RespiratoryHPIData(BaseModel):
    inicio_sintomas: str = "No referido"
    evolucion: str = "No referido"
    sintomas_principales_respiratorios: str = "No referido"
    factores_desencadenantes: str = "No referido"
    tratamientos_previos: str = "No referido"
    estado_actual: str = "No referido"


class RespiratoryAntecedentesData(BaseModel):
    personales_respiratorios: list[str] = Field(default_factory=list)
    personales_cardiovasculares: list[str] = Field(default_factory=list)
    personales_quirurgicos: list[str] = Field(default_factory=list)
    medicamentos_actuales: list[str] = Field(default_factory=list)
    familiares_asma: list[str] = Field(default_factory=list)
    familiares_alergias: list[str] = Field(default_factory=list)
    familiares_enfermedades_pulmonares: list[str] = Field(default_factory=list)


class RespiratorySymptomChecklist(BaseModel):
    tos: str = "No mencionado"
    flema: str = "No mencionado"
    disnea: str = "No mencionado"
    sibilancias: str = "No mencionado"
    dolor_toracico: str = "No mencionado"
    congestion_nasal: str = "No mencionado"
    ronquidos: str = "No mencionado"
    apneas_sueno: str = "No mencionado"
    fatiga_ejercicio: str = "No mencionado"


class RespiratoryEvaluationData(BaseModel):
    patron_respiratorio_observado: str = "No referido"
    tipo_respiracion: str = "No referido"
    uso_musculos_accesorios: str = "No referido"
    tolerancia_ejercicio: str = "No referido"
    calidad_respiracion: str = "No referido"
    hallazgos_relevantes_mencionados_por_terapeuta: str = "No referido"


class RespiratoryTemplateOutput(BaseModel):
    datos_personales_paciente: RespiratoryPatientPersonalData = Field(
        default_factory=RespiratoryPatientPersonalData
    )
    datos_identificacion: RespiratoryIdentificationData = Field(
        default_factory=RespiratoryIdentificationData
    )
    enfermedad_actual_hpi: RespiratoryHPIData = Field(default_factory=RespiratoryHPIData)
    antecedentes_relevantes: RespiratoryAntecedentesData = Field(
        default_factory=RespiratoryAntecedentesData
    )
    sintomas_respiratorios_checklist: RespiratorySymptomChecklist = Field(
        default_factory=RespiratorySymptomChecklist
    )
    evaluacion_clinica_respiratoria: RespiratoryEvaluationData = Field(
        default_factory=RespiratoryEvaluationData
    )
    pruebas_realizadas_en_consulta: list[str] = Field(default_factory=list)
    impresion_clinica: str = "No referido"
    plan_terapeutico: list[str] = Field(default_factory=list)


class ClinicalStructuredOutput(BaseModel):
    metadata: ClinicalMetadata
    identificacion_minima: dict[str, Any]
    motivo_consulta: str
    resumen_sesion: str
    sintomas_o_malestares_referidos: list[str]
    antecedentes_mencionados: list[str]
    contexto_familiar_social_laboral: list[str]
    factores_estresores_actuales: list[str]
    factores_protectores: list[str]
    riesgos_mencionados: list[str]
    frases_textuales_clave: list[str]
    hipotesis_iniciales_para_revision: list[str]
    plan_o_proximos_pasos: list[str]
    campos_inciertos_o_ambiguos: list[str]
    plantilla_historia_clinica_respiratoria: RespiratoryTemplateOutput = Field(
        default_factory=RespiratoryTemplateOutput
    )


class ClinicalDraftOut(BaseModel):
    id: str
    session_id: str
    version: int
    llm_model: str
    prompt_version: str
    status: ClinicalDraftStatus
    structured_json: dict[str, Any]
    session_summary: str
    clinical_profile_text: str
    therapist_review_notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewDraftRequest(BaseModel):
    therapist_review_notes: str | None = None
    clinical_profile_text: str | None = None
    session_summary: str | None = None


class GeneratedDocumentOut(BaseModel):
    id: str
    session_id: str
    clinical_draft_id: str
    google_doc_id: str | None
    google_doc_url: str | None
    exported_docx_path: str | None
    exported_docx_mime_type: str | None
    exported_pdf_path: str | None
    exported_pdf_mime_type: str | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RiskFlagOut(BaseModel):
    id: str
    session_id: str
    severity: RiskSeverity
    category: RiskCategory
    snippet: str
    rationale: str
    requires_human_review: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: str
    actor_type: AuditActorType
    actor_id: str | None
    entity_type: str
    entity_id: str
    action: str
    metadata: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class WorkspaceEventPayload(BaseModel):
    event_type: str = Field(..., alias="eventType")
    conference_record_name: str | None = Field(default=None, alias="conferenceRecordName")
    transcript_name: str | None = Field(default=None, alias="transcriptName")
    session_id: str | None = Field(default=None, alias="sessionId")
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _capture_payload(cls, values: Any) -> Any:
        if isinstance(values, dict):
            data = dict(values)
            data["raw_payload"] = dict(values)
            return data
        return values


class RiskFlagCandidate(BaseModel):
    severity: RiskSeverity
    category: RiskCategory
    snippet: str
    rationale: str
    requires_human_review: bool = True


class ClinicalGenerationResult(BaseModel):
    structured_output: ClinicalStructuredOutput
    session_summary: str
    clinical_profile_text: str
    risk_flags: list[RiskFlagCandidate] = Field(default_factory=list)

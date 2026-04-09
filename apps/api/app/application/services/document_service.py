"""Service for generated Google documents."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditService
from app.core.config import settings
from app.domain.enums import AuditActorType, DocumentStatus
from app.domain.models import ClinicalDraft, GeneratedDocument, Session as SessionModel
from app.infrastructure.adapters.google_docs_adapter import BaseDocsAdapter, build_docs_adapter


class DocumentGenerationService:
    """Create and export therapist-facing draft documents."""

    _PLACEHOLDER_VALUES = {
        "no referido",
        "no mencionad",
        "n/a",
        "na",
        "none",
        "null",
        "sin dato",
    }

    def __init__(self, db: Session, docs_adapter: BaseDocsAdapter | None = None) -> None:
        self.db = db
        self.adapter = docs_adapter
        self.audit = AuditService(db)

    def create_document(self, session: SessionModel, draft: ClinicalDraft) -> GeneratedDocument:
        title = self._build_title(session, draft)
        body = self._build_body(session, draft)

        adapter = self.adapter or build_docs_adapter(
            therapist=session.therapist,
            impersonated_user=session.therapist.google_account_email if session.therapist else None,
        )
        doc_id, doc_url = adapter.create_document(title=title, content=body)
        generated = GeneratedDocument(
            session_id=session.id,
            clinical_draft_id=draft.id,
            google_doc_id=doc_id,
            google_doc_url=doc_url,
            status=DocumentStatus.created,
        )
        self.db.add(generated)
        self.db.flush()

        self.audit.log(
            actor_type=AuditActorType.system,
            entity_type="generated_document",
            entity_id=generated.id,
            action="document.created",
            metadata={"session_id": session.id, "draft_id": draft.id, "doc_id": doc_id},
        )
        return generated

    def export_docx(self, document: GeneratedDocument) -> GeneratedDocument:
        return self._export(document=document, format_name="docx")

    def export_pdf(self, document: GeneratedDocument) -> GeneratedDocument:
        return self._export(document=document, format_name="pdf")

    def _export(self, *, document: GeneratedDocument, format_name: str) -> GeneratedDocument:
        if not document.google_doc_id:
            document.status = DocumentStatus.failed
            self.db.add(document)
            raise ValueError("Cannot export document without google_doc_id")

        destination = f"{settings.artifacts_dir}/exports"
        session = self.db.scalar(select(SessionModel).where(SessionModel.id == document.session_id))
        therapist = session.therapist if session and session.therapist else None

        adapter = self.adapter or build_docs_adapter(
            therapist=therapist,
            impersonated_user=therapist.google_account_email if therapist else None,
        )

        if format_name == "docx":
            file_path, mime_type = adapter.export_docx(
                doc_id=document.google_doc_id,
                destination_dir=destination,
                template_docx_path=therapist.template_docx_path if therapist else None,
            )
            document.exported_docx_path = file_path
            document.exported_docx_mime_type = mime_type
            audit_action = "document.exported_docx"
            metadata_key = "docx_path"
        else:
            file_path, mime_type = adapter.export_pdf(
                doc_id=document.google_doc_id,
                destination_dir=destination,
                template_pdf_path=therapist.template_pdf_path if therapist else None,
                signature_image_path=therapist.signature_image_path if therapist else None,
                therapist_name=therapist.full_name if therapist else None,
            )
            document.exported_pdf_path = file_path
            document.exported_pdf_mime_type = mime_type
            audit_action = "document.exported_pdf"
            metadata_key = "pdf_path"

        document.status = DocumentStatus.exported
        self.db.add(document)

        self.audit.log(
            actor_type=AuditActorType.system,
            entity_type="generated_document",
            entity_id=document.id,
            action=audit_action,
            metadata={metadata_key: file_path, "mime_type": mime_type},
        )
        return document

    def delete_document(self, document: GeneratedDocument, *, actor_id: str | None = None) -> None:
        removed_files = 0

        for candidate in [document.exported_docx_path, document.exported_pdf_path]:
            if not candidate:
                continue
            path = Path(candidate)
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
                removed_files += 1

        if document.google_doc_id:
            payload_path = Path(settings.artifacts_dir) / f"{document.google_doc_id}.gdoc.mock.json"
            if payload_path.exists() and payload_path.is_file():
                payload_path.unlink(missing_ok=True)
                removed_files += 1

        document_id = document.id
        session_id = document.session_id
        self.db.delete(document)
        self.db.flush()

        self.audit.log(
            actor_type=AuditActorType.therapist if actor_id else AuditActorType.system,
            actor_id=actor_id,
            entity_type="generated_document",
            entity_id=document_id,
            action="document.deleted",
            metadata={"session_id": session_id, "removed_files": removed_files},
        )

    def _build_title(self, session: SessionModel, draft: ClinicalDraft) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
        patient_code = session.patient.external_patient_id or session.patient.id[:8]
        return f"Perfil Clinico {patient_code} Sesion {stamp} v{draft.version}"

    def _build_body(self, session: SessionModel, draft: ClinicalDraft) -> str:
        therapist_name = session.therapist.full_name

        structured = draft.structured_json if isinstance(draft.structured_json, dict) else {}
        template_data = self._template_data(structured)

        checklist = template_data.get("sintomas_respiratorios_checklist", {})
        if not isinstance(checklist, dict):
            checklist = {}

        antecedentes = template_data.get("antecedentes_relevantes", {})
        if not isinstance(antecedentes, dict):
            antecedentes = {}

        evaluacion = template_data.get("evaluacion_clinica_respiratoria", {})
        if not isinstance(evaluacion, dict):
            evaluacion = {}

        hpi = template_data.get("enfermedad_actual_hpi", {})
        if not isinstance(hpi, dict):
            hpi = {}

        personal = template_data.get("datos_personales_paciente", {})
        if not isinstance(personal, dict):
            personal = {}

        identification = template_data.get("datos_identificacion", {})
        if not isinstance(identification, dict):
            identification = {}

        identificacion_minima = structured.get("identificacion_minima", {})
        if not isinstance(identificacion_minima, dict):
            identificacion_minima = {}

        patient_full_name = (
            f"{(session.patient.first_name or '').strip()} {(session.patient.last_name or '').strip()}".strip()
        )
        patient_name = self._first_meaningful(
            patient_full_name,
            personal.get("nombre_paciente"),
            identification.get("nombre_paciente"),
            identificacion_minima.get("nombre_paciente"),
        )
        age_label = self._resolve_age_label(session, identification, identificacion_minima)
        date_label = self._resolve_session_date(session, identification)
        birth_date_label = self._resolve_birth_date(session, personal)
        city_label = self._resolve_city(session, personal)

        phone_label = self._first_meaningful(session.patient.phone, personal.get("telefono"))
        id_label = self._first_meaningful(session.patient.external_patient_id, personal.get("identificacion"))
        address_label = self._first_meaningful(session.patient.address, personal.get("direccion"))
        profession_label = self._first_meaningful(session.patient.profession, personal.get("profesion"))
        email_label = self._first_meaningful(session.patient.email, personal.get("email"))
        sexo_label = self._first_meaningful(identification.get("sexo"), session.patient.gender)
        motivo_label = self._first_meaningful(identification.get("motivo_consulta"), structured.get("motivo_consulta"))

        plan_items = self._to_list(template_data.get("plan_terapeutico")) or self._to_list(
            structured.get("plan_o_proximos_pasos")
        )
        risk_items = self._to_list(structured.get("riesgos_mencionados"))
        pruebas_items = self._to_list(template_data.get("pruebas_realizadas_en_consulta"))

        impresion = self._not_referido(
            self._first_meaningful(
                template_data.get("impresion_clinica"),
                structured.get("resumen_sesion"),
                draft.session_summary,
            )
        )

        lines = [
            "Borrador generado por IA. Requiere revision y validacion profesional.",
            "",
            "DATOS PERSONALES DEL PACIENTE",
            f"- Nombre: {self._not_referido(patient_name)}",
            f"- Telefono: {self._not_referido(phone_label)}",
            f"- Identificacion: {self._not_referido(id_label)}",
            f"- Fecha de nacimiento: {self._not_referido(birth_date_label)}",
            f"- Direccion: {self._not_referido(address_label)}",
            f"- Ciudad: {self._not_referido(city_label)}",
            f"- Profesion: {self._not_referido(profession_label)}",
            f"- Email: {self._not_referido(email_label)}",
            "",
            "1) DATOS DE IDENTIFICACION",
            f"- Nombre del paciente: {self._not_referido(self._first_meaningful(identification.get('nombre_paciente'), patient_name))}",
            f"- Edad: {age_label}",
            f"- Sexo: {self._not_referido(sexo_label)}",
            f"- Fecha consulta: {date_label}",
            f"- Motivo de consulta: {self._not_referido(motivo_label)}",
            "",
            "2) ENFERMEDAD ACTUAL (HPI)",
            f"- Inicio de sintomas: {self._not_referido(hpi.get('inicio_sintomas'))}",
            f"- Evolucion: {self._not_referido(hpi.get('evolucion'))}",
            f"- Sintomas respiratorios principales: {self._not_referido(hpi.get('sintomas_principales_respiratorios'))}",
            f"- Factores desencadenantes: {self._not_referido(hpi.get('factores_desencadenantes'))}",
            f"- Tratamientos previos: {self._not_referido(hpi.get('tratamientos_previos'))}",
            f"- Estado actual: {self._not_referido(self._first_meaningful(hpi.get('estado_actual'), structured.get('resumen_sesion')))}",
            "",
            "3) ANTECEDENTES RELEVANTES",
            "Personales",
            f"- Respiratorios: {self._not_referido(self._join_list(antecedentes.get('personales_respiratorios')))}",
            f"- Cardiovasculares: {self._not_referido(self._join_list(antecedentes.get('personales_cardiovasculares')))}",
            f"- Quirurgicos: {self._not_referido(self._join_list(antecedentes.get('personales_quirurgicos')))}",
            f"- Medicamentos actuales: {self._not_referido(self._join_list(antecedentes.get('medicamentos_actuales')))}",
            "Familiares",
            f"- Asma: {self._not_referido(self._join_list(antecedentes.get('familiares_asma')))}",
            f"- Alergias: {self._not_referido(self._join_list(antecedentes.get('familiares_alergias')))}",
            f"- Enfermedades pulmonares: {self._not_referido(self._join_list(antecedentes.get('familiares_enfermedades_pulmonares')))}",
            "",
            "4) SINTOMAS RESPIRATORIOS ACTUALES (CHECKLIST)",
            f"- Tos: {self._check_status(checklist.get('tos'))}",
            f"- Flema: {self._check_status(checklist.get('flema'))}",
            f"- Disnea: {self._check_status(checklist.get('disnea'))}",
            f"- Sibilancias: {self._check_status(checklist.get('sibilancias'))}",
            f"- Dolor toracico: {self._check_status(checklist.get('dolor_toracico'))}",
            f"- Congestion nasal: {self._check_status(checklist.get('congestion_nasal'))}",
            f"- Ronquidos: {self._check_status(checklist.get('ronquidos'))}",
            f"- Apneas sueno: {self._check_status(checklist.get('apneas_sueno'))}",
            f"- Fatiga ejercicio: {self._check_status(checklist.get('fatiga_ejercicio'))}",
            "",
            "5) EVALUACION CLINICA RESPIRATORIA",
            f"- Patron respiratorio observado: {self._not_referido(evaluacion.get('patron_respiratorio_observado'))}",
            f"- Tipo de respiracion (oral/nasal): {self._not_referido(evaluacion.get('tipo_respiracion'))}",
            f"- Uso de musculos accesorios: {self._not_referido(evaluacion.get('uso_musculos_accesorios'))}",
            f"- Tolerancia ejercicio: {self._not_referido(evaluacion.get('tolerancia_ejercicio'))}",
            f"- Calidad de la respiracion: {self._not_referido(evaluacion.get('calidad_respiracion'))}",
            f"- Hallazgos relevantes mencionados por terapeuta: {self._not_referido(evaluacion.get('hallazgos_relevantes_mencionados_por_terapeuta'))}",
            "",
            "6) PRUEBAS REALIZADAS EN CONSULTA",
        ]

        if pruebas_items:
            lines.extend(f"- {item}" for item in pruebas_items)
        else:
            lines.append("- No referido")

        lines.extend(["", "7) IMPRESION CLINICA", impresion, "", "8) PLAN TERAPEUTICO"])

        if plan_items:
            lines.extend(f"- {item}" for item in plan_items)
        else:
            lines.append("- No referido")

        if risk_items:
            lines.extend(["", "RIESGOS Y ALERTAS (PARA REVISION)"])
            lines.extend(f"- {item}" for item in risk_items)

        lines.extend(
            [
                "",
                f"Terapeuta: {therapist_name}",
                f"Sesion ID: {session.id}",
                f"Version del borrador: v{draft.version}",
                f"Prompt version: {draft.prompt_version}",
                f"Modelo: {draft.llm_model}",
            ]
        )

        return "\n".join(lines)

    def _resolve_age_label(
        self,
        session: SessionModel,
        identification: dict[str, Any],
        identificacion_minima: dict[str, Any],
    ) -> str:
        value = self._first_meaningful(
            session.patient.age,
            identification.get("edad"),
            identificacion_minima.get("edad_referida"),
        )
        if value is None:
            return "No referido"
        return str(value)

    def _resolve_session_date(self, session: SessionModel, identification: dict[str, Any]) -> str:
        from_ident = self._first_meaningful(identification.get("fecha_consulta"))
        if from_ident is not None:
            return str(from_ident)

        dt = session.session_ended_at or session.session_started_at
        if isinstance(dt, datetime):
            return dt.strftime("%d/%m/%Y")
        return datetime.now(UTC).strftime("%d/%m/%Y")

    def _resolve_birth_date(self, session: SessionModel, personal: dict[str, Any]) -> str:
        value = self._first_meaningful(session.patient.birth_date, personal.get("fecha_nacimiento"))
        return self._format_date_value(value, date_format="%Y-%m-%d")

    def _resolve_city(self, session: SessionModel, personal: dict[str, Any]) -> str:
        direct = self._first_meaningful(session.patient.city, personal.get("ciudad"))
        if direct is not None:
            return str(direct)

        address = self._first_meaningful(session.patient.address, personal.get("direccion"))
        if address is None:
            return "No referido"

        chunks = [segment.strip() for segment in str(address).split(",") if segment.strip()]
        if not chunks:
            return "No referido"
        return chunks[-1]

    def _template_data(self, structured: dict[str, Any]) -> dict[str, Any]:
        template = structured.get("plantilla_historia_clinica_respiratoria")
        return template if isinstance(template, dict) else {}

    def _to_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if self._is_meaningful(item)]
        if self._is_meaningful(value):
            return [str(value).strip()]
        return []

    def _join_list(self, value: Any) -> str:
        items = self._to_list(value)
        return "; ".join(items) if items else ""

    def _check_status(self, value: Any) -> str:
        status = str(value or "").strip().lower()
        if "presen" in status:
            return "Presente"
        if "ausen" in status or status in {"no", "negado", "negada"}:
            return "Ausente"
        return "No mencionado"

    def _not_referido(self, value: Any) -> str:
        if not self._is_meaningful(value):
            return "No referido"
        if isinstance(value, (date, datetime)):
            return self._format_date_value(value, date_format="%Y-%m-%d")
        return str(value).strip()

    def _is_meaningful(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (date, datetime, int, float)):
            return True

        cleaned = str(value).strip()
        if not cleaned:
            return False

        lowered = cleaned.lower()
        if lowered in self._PLACEHOLDER_VALUES:
            return False
        if lowered.startswith("no referido") or lowered.startswith("no mencion") or lowered.startswith("sin dato"):
            return False
        return True

    def _first_meaningful(self, *values: Any) -> Any | None:
        for value in values:
            if self._is_meaningful(value):
                return value
        return None

    def _format_date_value(self, value: Any, *, date_format: str) -> str:
        if isinstance(value, datetime):
            return value.strftime(date_format)
        if isinstance(value, date):
            return value.strftime(date_format)
        if self._is_meaningful(value):
            return str(value).strip()
        return "No referido"

    def latest_document_for_draft(self, draft_id: str) -> GeneratedDocument | None:
        return self.db.scalar(
            select(GeneratedDocument)
            .where(GeneratedDocument.clinical_draft_id == draft_id)
            .order_by(GeneratedDocument.created_at.desc())
            .limit(1)
        )







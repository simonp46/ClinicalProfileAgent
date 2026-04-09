"""Clinical draft generation service."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditService
from app.application.services.prompt_registry import PromptRegistry
from app.application.services.session_service import SessionService
from app.application.services.template_format_service import TemplateFormatService
from app.core.config import settings
from app.domain.enums import AuditActorType, ClinicalDraftStatus, RiskCategory, RiskSeverity, SessionStatus
from app.domain.models import (
    ClinicalDraft,
    GeneratedDocument,
    RiskFlag,
    Session as SessionModel,
    Transcript,
)
from app.domain.schemas import ClinicalGenerationResult, RiskFlagCandidate
from app.infrastructure.adapters.openai_adapter import BaseLLMAdapter, build_llm_adapter


class ClinicalDraftService:
    """Generate structured clinical drafts from de-identified transcripts."""

    def __init__(self, db: Session, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.db = db
        self.adapter = llm_adapter or build_llm_adapter()
        self.audit = AuditService(db)
        self.session_service = SessionService(db)
        self.prompt_registry = PromptRegistry(db)
        self.template_format_service = TemplateFormatService()

    def generate_for_session(self, session: SessionModel, *, regenerate: bool = False) -> ClinicalDraft:
        transcript = self.db.scalar(select(Transcript).where(Transcript.session_id == session.id))
        if transcript is None:
            raise ValueError("Transcript not found for session")

        if regenerate:
            self._hard_reset_session_outputs(session_id=session.id)

        self.prompt_registry.ensure_seeded(["clinical_draft"])
        prompt = self.prompt_registry.get_prompt("clinical_draft")
        chunks = self._chunk_text(transcript.deidentified_text)
        chunk_outputs = [
            self.adapter.generate_clinical_artifacts(prompt=prompt, transcript_chunk=chunk)
            for chunk in chunks
        ]
        result = self._synthesize(chunk_outputs)

        draft_version = 1 if regenerate else self.session_service.next_draft_version(session.id)
        structured_payload = result.structured_output.model_dump()
        metadata = structured_payload.get("metadata", {})
        metadata["source_hash"] = transcript.source_hash
        metadata["reset_from_scratch"] = regenerate
        structured_payload["metadata"] = metadata

        template_adapted_profile = self.template_format_service.adapt_profile_text(
            therapist=session.therapist,
            session=session,
            structured_output=structured_payload,
            fallback_profile_text=result.clinical_profile_text,
            session_summary=result.session_summary,
            transcript_text=transcript.deidentified_text,
        )

        draft = ClinicalDraft(
            session_id=session.id,
            version=draft_version,
            llm_model=settings.openai_model if not settings.use_mock_openai else "mock-openai",
            prompt_version=settings.prompt_version,
            status=ClinicalDraftStatus.generated,
            structured_json=structured_payload,
            session_summary=result.session_summary,
            clinical_profile_text=template_adapted_profile,
        )
        self.db.add(draft)
        self.db.flush()

        self._replace_risk_flags(session.id, result)
        session.status = SessionStatus.ready_for_review
        self.db.add(session)

        self.audit.log(
            actor_type=AuditActorType.system,
            entity_type="clinical_draft",
            entity_id=draft.id,
            action="clinical_draft.generated",
            metadata={
                "session_id": session.id,
                "version": draft.version,
                "prompt_version": settings.prompt_version,
                "model": draft.llm_model,
                "regenerate": regenerate,
                "template_adapted": bool(
                    session.therapist
                    and (session.therapist.template_pdf_path or session.therapist.template_docx_path)
                ),
            },
        )
        return draft

    def approve_draft(
        self,
        draft: ClinicalDraft,
        reviewer_id: str,
        notes: str | None = None,
        edited_profile_text: str | None = None,
        edited_summary: str | None = None,
    ) -> ClinicalDraft:
        draft.status = ClinicalDraftStatus.approved
        draft.therapist_review_notes = notes
        if edited_profile_text:
            draft.clinical_profile_text = edited_profile_text
        if edited_summary:
            draft.session_summary = edited_summary
        self.db.add(draft)

        session = self.db.scalar(select(SessionModel).where(SessionModel.id == draft.session_id))
        if session:
            session.status = SessionStatus.approved
            self.db.add(session)

        self.audit.log(
            actor_type=AuditActorType.therapist,
            actor_id=reviewer_id,
            entity_type="clinical_draft",
            entity_id=draft.id,
            action="clinical_draft.approved",
            metadata={"notes": bool(notes), "edited": bool(edited_profile_text or edited_summary)},
        )
        return draft

    def reject_draft(
        self,
        draft: ClinicalDraft,
        reviewer_id: str,
        notes: str | None = None,
        edited_profile_text: str | None = None,
        edited_summary: str | None = None,
    ) -> ClinicalDraft:
        draft.status = ClinicalDraftStatus.reviewed
        draft.therapist_review_notes = notes
        if edited_profile_text:
            draft.clinical_profile_text = edited_profile_text
        if edited_summary:
            draft.session_summary = edited_summary
        self.db.add(draft)

        session = self.db.scalar(select(SessionModel).where(SessionModel.id == draft.session_id))
        if session:
            session.status = SessionStatus.processing
            self.db.add(session)

        self.audit.log(
            actor_type=AuditActorType.therapist,
            actor_id=reviewer_id,
            entity_type="clinical_draft",
            entity_id=draft.id,
            action="clinical_draft.rejected",
            metadata={"notes": bool(notes), "edited": bool(edited_profile_text or edited_summary)},
        )
        return draft

    def _hard_reset_session_outputs(self, *, session_id: str) -> None:
        documents = self.db.scalars(
            select(GeneratedDocument).where(GeneratedDocument.session_id == session_id)
        ).all()

        removed_files = 0
        exports_dir = Path(settings.artifacts_dir) / "exports"
        for document in documents:
            for candidate in [document.exported_docx_path, document.exported_pdf_path]:
                if candidate:
                    file_path = Path(candidate)
                    if file_path.exists() and file_path.is_file():
                        file_path.unlink(missing_ok=True)
                        removed_files += 1

            if document.google_doc_id:
                payload_path = Path(settings.artifacts_dir) / f"{document.google_doc_id}.gdoc.mock.json"
                if payload_path.exists() and payload_path.is_file():
                    payload_path.unlink(missing_ok=True)
                    removed_files += 1

                if exports_dir.exists():
                    for exported in exports_dir.glob(f"{document.google_doc_id}.*"):
                        if exported.is_file():
                            exported.unlink(missing_ok=True)
                            removed_files += 1

            self.db.delete(document)

        drafts = self.db.scalars(select(ClinicalDraft).where(ClinicalDraft.session_id == session_id)).all()
        for draft in drafts:
            self.db.delete(draft)

        flags = self.db.scalars(select(RiskFlag).where(RiskFlag.session_id == session_id)).all()
        for flag in flags:
            self.db.delete(flag)
        self.db.flush()

        self.audit.log(
            actor_type=AuditActorType.system,
            entity_type="session",
            entity_id=session_id,
            action="session.outputs_reset_from_scratch",
            metadata={
                "deleted_documents": len(documents),
                "deleted_drafts": len(drafts),
                "deleted_risk_flags": len(flags),
                "deleted_files": removed_files,
            },
        )

    def _chunk_text(self, text: str, chunk_size: int = 5000) -> list[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            boundary = text.rfind("\n", start, end)
            if boundary <= start:
                boundary = end
            chunks.append(text[start:boundary].strip())
            start = boundary
        return [chunk for chunk in chunks if chunk]

    def _synthesize(self, outputs: list[ClinicalGenerationResult]) -> ClinicalGenerationResult:
        if len(outputs) == 1:
            return outputs[0]

        base = outputs[0].model_copy(deep=True)

        list_fields = [
            "sintomas_o_malestares_referidos",
            "antecedentes_mencionados",
            "contexto_familiar_social_laboral",
            "factores_estresores_actuales",
            "factores_protectores",
            "riesgos_mencionados",
            "frases_textuales_clave",
            "hipotesis_iniciales_para_revision",
            "plan_o_proximos_pasos",
            "campos_inciertos_o_ambiguos",
        ]

        for field in list_fields:
            merged = OrderedDict()
            for output in outputs:
                for item in getattr(output.structured_output, field):
                    merged[item] = True
            setattr(base.structured_output, field, list(merged.keys()))

        summaries = [output.session_summary.strip() for output in outputs if output.session_summary.strip()]
        base.session_summary = " ".join(dict.fromkeys(summaries))

        profile_parts = [
            output.clinical_profile_text.strip() for output in outputs if output.clinical_profile_text.strip()
        ]
        base.clinical_profile_text = "\n\n".join(dict.fromkeys(profile_parts))

        risk_flags: list[RiskFlagCandidate] = []
        for output in outputs:
            risk_flags.extend(output.risk_flags)
        base.risk_flags = risk_flags
        return base

    def _replace_risk_flags(self, session_id: str, result: ClinicalGenerationResult) -> None:
        existing = self.db.scalars(select(RiskFlag).where(RiskFlag.session_id == session_id)).all()
        for flag in existing:
            self.db.delete(flag)

        candidates = list(result.risk_flags)
        if not candidates:
            candidates = self._heuristic_flags(result.structured_output.riesgos_mencionados)

        for item in candidates:
            self.db.add(
                RiskFlag(
                    session_id=session_id,
                    severity=item.severity,
                    category=item.category,
                    snippet=item.snippet,
                    rationale=item.rationale,
                    requires_human_review=item.requires_human_review,
                )
            )

    def _heuristic_flags(self, mentions: list[str]) -> list[RiskFlagCandidate]:
        flags: list[RiskFlagCandidate] = []
        for mention in mentions:
            lowered = mention.lower()
            category = RiskCategory.other
            severity = RiskSeverity.low
            if "suicid" in lowered:
                category = RiskCategory.suicide_risk
                severity = RiskSeverity.critical
            elif "autoles" in lowered or "me corto" in lowered:
                category = RiskCategory.self_harm
                severity = RiskSeverity.high
            elif "violencia" in lowered:
                category = RiskCategory.violence
                severity = RiskSeverity.high
            elif "abuso" in lowered:
                category = RiskCategory.abuse
                severity = RiskSeverity.high
            elif "psicos" in lowered:
                category = RiskCategory.psychosis
                severity = RiskSeverity.high
            flags.append(
                RiskFlagCandidate(
                    severity=severity,
                    category=category,
                    snippet=mention,
                    rationale="Extraido de riesgos_mencionados en salida estructurada.",
                    requires_human_review=True,
                )
            )
        return flags



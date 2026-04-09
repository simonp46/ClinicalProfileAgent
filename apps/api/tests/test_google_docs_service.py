import json
from pathlib import Path

from docx import Document
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.document_service import DocumentGenerationService
from app.application.services.pipeline_service import PipelineService
from app.application.services.prompt_registry import PromptRegistry
from app.core.config import settings
from app.domain.models import Session as SessionModel
from app.infrastructure.adapters.google_docs_adapter import MockDocsAdapter
from tests.helpers import seed_therapist_and_session


def test_document_generation_and_export_with_mock_adapter(db_session: Session) -> None:
    _, session_id = seed_therapist_and_session(db_session)
    session = db_session.scalar(select(SessionModel).where(SessionModel.id == session_id))
    assert session is not None

    session.patient.first_name = "Carlos"
    session.patient.last_name = "Mendez"
    session.patient.age = 36
    session.patient.birth_date = None
    session.patient.city = "Bogota"
    db_session.add(session.patient)

    registry = PromptRegistry(db_session)
    registry.ensure_seeded(["clinical_draft"])

    pipeline = PipelineService(db_session)
    pipeline.ingest_from_meet(session)
    draft = pipeline.generate_draft(session)

    service = DocumentGenerationService(db_session)
    generated = service.create_document(session, draft)
    exported_docx = service.export_docx(generated)
    exported_pdf = service.export_pdf(generated)

    db_session.commit()

    assert generated.google_doc_id is not None

    payload_path = Path(settings.artifacts_dir) / f"{generated.google_doc_id}.gdoc.mock.json"
    assert payload_path.exists()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    content = str(payload.get("content", ""))

    assert "DATOS PERSONALES DEL PACIENTE" in content
    assert "1) DATOS DE IDENTIFICACION" in content
    assert "2) ENFERMEDAD ACTUAL (HPI)" in content
    assert "8) PLAN TERAPEUTICO" in content
    assert "- Nombre del paciente: Carlos Mendez" in content
    assert "- Edad: 36" in content
    assert "- Ciudad: Bogota" in content
    assert "- Fecha consulta: No referido" not in content

    assert exported_docx.exported_docx_path is not None
    assert Path(exported_docx.exported_docx_path).exists()

    assert exported_pdf.exported_pdf_path is not None
    assert Path(exported_pdf.exported_pdf_path).exists()

    assert exported_pdf.status.value == "exported"


def test_export_docx_with_uploaded_template_is_legible(db_session: Session) -> None:
    _, session_id = seed_therapist_and_session(db_session)
    session = db_session.scalar(select(SessionModel).where(SessionModel.id == session_id))
    assert session is not None

    template_path = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "templates"
        / "plantilla_historia_clinica_respira_integral_editable_final.docx"
    )
    assert template_path.exists()

    session.therapist.template_docx_path = str(template_path)
    db_session.add(session.therapist)

    registry = PromptRegistry(db_session)
    registry.ensure_seeded(["clinical_draft"])

    pipeline = PipelineService(db_session)
    pipeline.ingest_from_meet(session)
    draft = pipeline.generate_draft(session)

    service = DocumentGenerationService(db_session)
    generated = service.create_document(session, draft)
    exported_docx = service.export_docx(generated)

    assert exported_docx.exported_docx_path is not None
    output_path = Path(exported_docx.exported_docx_path)
    assert output_path.exists()

    rendered = Document(output_path)
    rendered_text = "\n".join(p.text.strip() for p in rendered.paragraphs if p.text.strip())

    assert "Historia clínica respiratoria" in rendered_text
    assert "Seguimiento, intervención propuesta y recomendaciones" in rendered_text


def test_mock_adapter_uses_default_pdf_template_when_profile_template_missing(tmp_path: Path) -> None:
    adapter = MockDocsAdapter()

    missing_profile_pdf = tmp_path / "missing-template.pdf"
    resolved = adapter._resolve_template(str(missing_profile_pdf))

    expected = adapter.default_respiro_pdf if adapter.default_respiro_pdf.exists() else None
    assert resolved == expected


def test_mock_adapter_prefers_custom_profile_template(tmp_path: Path) -> None:
    adapter = MockDocsAdapter()
    custom = tmp_path / "custom-template.pdf"
    custom.write_bytes(b"%PDF-1.4\n%custom")

    resolved = adapter._resolve_template(str(custom))

    assert resolved == custom



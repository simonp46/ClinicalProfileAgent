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
from app.infrastructure.adapters.google_docs_adapter import GoogleDocsAdapter, MockDocsAdapter
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


def test_mock_adapter_uses_default_pdf_template_when_profile_template_missing(
    tmp_path: Path,
) -> None:
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


def test_google_adapter_renders_pdf_with_template_when_available(tmp_path: Path) -> None:
    def paragraph(text: str) -> dict[str, object]:
        return {"paragraph": {"elements": [{"textRun": {"content": text}}]}}

    class FakeDocsService:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def documents(self) -> "FakeDocsService":
            return self

        def get(self, **kwargs: object) -> "FakeDocsService":
            assert kwargs["documentId"] == "google-doc-123"
            return self

        def execute(self) -> dict[str, object]:
            return self.payload

    class FakeRenderer:
        def __init__(self) -> None:
            self.render_pdf_called = False
            self.last_kwargs: dict[str, object] = {}

        def render_pdf(self, **kwargs: object) -> bool:
            self.render_pdf_called = True
            self.last_kwargs = kwargs
            Path(str(kwargs["output_path"])).write_bytes(b"%PDF-1.4\n%templated")
            return True

    payload = {
        "body": {
            "content": [
                paragraph("DATOS PERSONALES DEL PACIENTE\n"),
                paragraph("- Nombre del paciente: Carlos Mendez\n"),
                paragraph("- Edad: 36\n"),
                paragraph("- Fecha consulta: 10/04/2026\n"),
                paragraph("- Ciudad: Bogota\n"),
                paragraph("1) DATOS DE IDENTIFICACION\n"),
                paragraph("Paciente con seguimiento respiratorio.\n"),
            ]
        }
    }

    template_path = tmp_path / "template.pdf"
    template_path.write_bytes(b"%PDF-1.4\n%template")
    signature_path = tmp_path / "signature.png"

    adapter = GoogleDocsAdapter.__new__(GoogleDocsAdapter)
    adapter.docs_service = FakeDocsService(payload)
    adapter.drive_service = None
    adapter.default_respiro_docx = tmp_path / "missing.docx"
    adapter.default_respiro_pdf = template_path
    adapter.respiro_renderer = FakeRenderer()

    output_path, mime_type = adapter.export_pdf(
        doc_id="google-doc-123",
        destination_dir=str(tmp_path / "exports"),
        signature_image_path=str(signature_path),
        therapist_name="Dra. Respira",
    )

    assert mime_type == "application/pdf"
    assert Path(output_path).exists()
    assert adapter.respiro_renderer.render_pdf_called is True
    assert adapter.respiro_renderer.last_kwargs["template_path"] == str(template_path)
    assert adapter.respiro_renderer.last_kwargs["therapist_name"] == "Dra. Respira"
    assert adapter.respiro_renderer.last_kwargs["signature_image_path"] == str(signature_path)

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.document_service import DocumentGenerationService
from app.application.services.pipeline_service import PipelineService
from app.application.services.prompt_registry import PromptRegistry
from app.domain.models import Session as SessionModel
from app.infrastructure.adapters.google_docs_adapter import BaseDocsAdapter
from tests.helpers import seed_therapist_and_session


class RecordingDocsAdapter(BaseDocsAdapter):
    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self.destination.mkdir(parents=True, exist_ok=True)
        self.last_docx_template: str | None = None
        self.last_pdf_template: str | None = None
        self.last_pdf_signature: str | None = None
        self.last_pdf_therapist_name: str | None = None

    def create_document(self, *, title: str, content: str) -> tuple[str, str]:
        _ = title
        _ = content
        return "mock-doc-id", "file:///mock-doc-id"

    def export_docx(
        self,
        *,
        doc_id: str,
        destination_dir: str,
        template_docx_path: str | None = None,
    ) -> tuple[str, str]:
        _ = destination_dir
        self.last_docx_template = template_docx_path
        output = self.destination / f"{doc_id}.docx"
        output.write_bytes(b"mock-docx")
        return str(output), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def export_pdf(
        self,
        *,
        doc_id: str,
        destination_dir: str,
        template_pdf_path: str | None = None,
        signature_image_path: str | None = None,
        therapist_name: str | None = None,
    ) -> tuple[str, str]:
        _ = destination_dir
        self.last_pdf_template = template_pdf_path
        self.last_pdf_signature = signature_image_path
        self.last_pdf_therapist_name = therapist_name
        output = self.destination / f"{doc_id}.pdf"
        output.write_bytes(b"%PDF-1.4\n%mock")
        return str(output), "application/pdf"


def test_document_export_uses_therapist_assets(db_session: Session, tmp_path: Path) -> None:
    _, session_id = seed_therapist_and_session(db_session)
    session = db_session.scalar(select(SessionModel).where(SessionModel.id == session_id))
    assert session is not None

    template_pdf = tmp_path / "template.pdf"
    template_pdf.write_bytes(b"%PDF-1.4\n%template")
    template_docx = tmp_path / "template.docx"
    template_docx.write_bytes(b"docx-template")
    signature_png = tmp_path / "signature.png"
    signature_png.write_bytes(b"png-signature")

    session.therapist.template_pdf_path = str(template_pdf)
    session.therapist.template_docx_path = str(template_docx)
    session.therapist.signature_image_path = str(signature_png)
    db_session.add(session.therapist)

    registry = PromptRegistry(db_session)
    registry.ensure_seeded(["clinical_draft"])

    pipeline = PipelineService(db_session)
    pipeline.ingest_from_meet(session)
    draft = pipeline.generate_draft(session)

    adapter = RecordingDocsAdapter(destination=tmp_path / "exports")
    service = DocumentGenerationService(db_session, docs_adapter=adapter)
    generated = service.create_document(session, draft)
    service.export_docx(generated)
    service.export_pdf(generated)

    assert adapter.last_docx_template == str(template_docx)
    assert adapter.last_pdf_template == str(template_pdf)
    assert adapter.last_pdf_signature == str(signature_png)
    assert adapter.last_pdf_therapist_name == session.therapist.full_name

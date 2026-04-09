import base64
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.infrastructure.adapters.google_docs_adapter import MockDocsAdapter

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aP8AAAAASUVORK5CYII="
)


def _create_template_with_widget_field(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=LETTER)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, 120, "Aceptacion y firmas")
    pdf.drawString(40, 95, "Responsable")
    pdf.acroForm.textfield(
        name="responsable_firma",
        tooltip="responsable",
        x=145,
        y=78,
        width=180,
        height=32,
        borderStyle="underlined",
        forceBorder=True,
    )
    pdf.save()


def _create_template_with_text(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=LETTER)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(45, 120, "Aceptacion y firmas")
    pdf.drawString(45, 92, "Responsable: ___________________")
    pdf.save()


def test_signature_anchor_prefers_widget_responsable_field(db_session: Session, tmp_path: Path) -> None:
    _ = db_session
    template_path = tmp_path / "widget-template.pdf"
    _create_template_with_widget_field(template_path)

    reader = PdfReader(str(template_path))
    adapter = MockDocsAdapter()
    anchor = adapter._resolve_signature_anchor(reader)

    assert anchor.source.startswith("widget:")
    assert anchor.page_index == 0
    assert anchor.x >= 140
    assert anchor.y >= 70


def test_signature_anchor_falls_back_to_text_responsable(db_session: Session, tmp_path: Path) -> None:
    _ = db_session
    template_path = tmp_path / "text-template.pdf"
    _create_template_with_text(template_path)

    reader = PdfReader(str(template_path))
    adapter = MockDocsAdapter()
    anchor = adapter._resolve_signature_anchor(reader)

    assert anchor.source == "text:responsable"
    assert anchor.page_index == 0


def test_export_pdf_uses_detected_anchor_without_errors(db_session: Session, tmp_path: Path) -> None:
    _ = db_session
    template_path = tmp_path / "widget-template.pdf"
    signature_path = tmp_path / "signature.png"
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    _create_template_with_widget_field(template_path)
    signature_path.write_bytes(_ONE_PIXEL_PNG)

    adapter = MockDocsAdapter()
    doc_id, _ = adapter.create_document(title="Demo", content="Nombre del paciente: Demo")
    exported_path, mime_type = adapter.export_pdf(
        doc_id=doc_id,
        destination_dir=str(output_dir),
        template_pdf_path=str(template_path),
        signature_image_path=str(signature_path),
        therapist_name="Terapeuta Demo",
    )

    assert mime_type == "application/pdf"
    assert Path(exported_path).exists()

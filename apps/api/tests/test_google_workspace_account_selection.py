from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.document_service import DocumentGenerationService
from app.application.services.pipeline_service import PipelineService
from app.application.services.prompt_registry import PromptRegistry
from app.domain.models import Session as SessionModel
from app.domain.schemas import TranscriptIngestRequest, TranscriptSegmentIn
from tests.helpers import seed_therapist_and_session


class _StubMeetAdapter:
    def fetch_transcript(
        self,
        session: SessionModel,
        *,
        transcript_name: str | None = None,
    ) -> TranscriptIngestRequest:
        _ = session
        _ = transcript_name
        return TranscriptIngestRequest(
            google_transcript_name="conferenceRecords/test/transcripts/real-1",
            google_docs_uri="https://docs.google.com/document/d/mock-transcript/edit",
            language_code="es",
            segments=[
                TranscriptSegmentIn(
                    sequence_no=1,
                    speaker_label="Terapeuta",
                    original_participant_ref="participants/therapist",
                    text="Buenos dias, revisemos la evolucion respiratoria.",
                    start_time=None,
                    end_time=None,
                ),
                TranscriptSegmentIn(
                    sequence_no=2,
                    speaker_label="Paciente",
                    original_participant_ref="participants/patient",
                    text="Presento disnea con esfuerzo y tos seca.",
                    start_time=None,
                    end_time=None,
                ),
            ],
        )


class _StubDocsAdapter:
    def create_document(self, *, title: str, content: str) -> tuple[str, str]:
        _ = title
        _ = content
        return "google-doc-123", "https://docs.google.com/document/d/google-doc-123/edit"

    def export_docx(
        self,
        *,
        doc_id: str,
        destination_dir: str,
        template_docx_path: str | None = None,
    ) -> tuple[str, str]:
        _ = doc_id
        _ = destination_dir
        _ = template_docx_path
        return "/tmp/mock.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def export_pdf(
        self,
        *,
        doc_id: str,
        destination_dir: str,
        template_pdf_path: str | None = None,
        signature_image_path: str | None = None,
        therapist_name: str | None = None,
    ) -> tuple[str, str]:
        _ = doc_id
        _ = destination_dir
        _ = template_pdf_path
        _ = signature_image_path
        _ = therapist_name
        return "/tmp/mock.pdf", "application/pdf"


def test_pipeline_uses_therapist_google_account_for_meet(monkeypatch, db_session: Session) -> None:
    _, session_id = seed_therapist_and_session(db_session)
    session = db_session.scalar(select(SessionModel).where(SessionModel.id == session_id))
    assert session is not None

    session.therapist.google_account_email = "real.user@workspace.com"
    db_session.add(session.therapist)

    captured: dict[str, object | None] = {}

    def fake_builder(*, therapist=None, impersonated_user: str | None = None):
        captured["therapist"] = therapist
        captured["impersonated_user"] = impersonated_user
        return _StubMeetAdapter()

    monkeypatch.setattr("app.application.services.pipeline_service.build_meet_adapter", fake_builder)

    pipeline = PipelineService(db_session)
    transcript_id = pipeline.ingest_from_meet(session, transcript_name="conferenceRecords/test/transcripts/real-1")

    assert transcript_id
    assert captured["therapist"] == session.therapist
    assert captured["impersonated_user"] == "real.user@workspace.com"


def test_document_service_uses_therapist_google_account_for_docs(monkeypatch, db_session: Session) -> None:
    _, session_id = seed_therapist_and_session(db_session)
    session = db_session.scalar(select(SessionModel).where(SessionModel.id == session_id))
    assert session is not None

    session.therapist.google_account_email = "real.user@workspace.com"
    db_session.add(session.therapist)

    registry = PromptRegistry(db_session)
    registry.ensure_seeded(["clinical_draft"])

    pipeline = PipelineService(db_session, meet_adapter=_StubMeetAdapter())
    pipeline.ingest_from_meet(session)
    draft = pipeline.generate_draft(session)

    captured: dict[str, object | None] = {}

    def fake_builder(*, therapist=None, impersonated_user: str | None = None):
        captured["therapist"] = therapist
        captured["impersonated_user"] = impersonated_user
        return _StubDocsAdapter()

    monkeypatch.setattr("app.application.services.document_service.build_docs_adapter", fake_builder)

    service = DocumentGenerationService(db_session)
    generated = service.create_document(session, draft)

    assert generated.google_doc_id == "google-doc-123"
    assert captured["therapist"] == session.therapist
    assert captured["impersonated_user"] == "real.user@workspace.com"

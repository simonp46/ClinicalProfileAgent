from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.pipeline_service import PipelineService
from app.application.services.prompt_registry import PromptRegistry
from app.domain.models import RiskFlag, Session
from tests.helpers import seed_therapist_and_session


def test_mock_ai_generation_creates_draft_and_risk_flags(db_session: Session) -> None:
    _, session_id = seed_therapist_and_session(db_session)
    session = db_session.scalar(select(Session).where(Session.id == session_id))
    assert session is not None

    registry = PromptRegistry(db_session)
    registry.ensure_seeded(["clinical_draft"])

    pipeline = PipelineService(db_session)
    pipeline.ingest_from_meet(session)
    draft = pipeline.generate_draft(session)
    db_session.commit()

    assert draft.session_summary
    assert draft.structured_json.get("metadata", {}).get("requires_human_review") is True

    flags = db_session.scalars(select(RiskFlag).where(RiskFlag.session_id == session_id)).all()
    assert len(flags) >= 1

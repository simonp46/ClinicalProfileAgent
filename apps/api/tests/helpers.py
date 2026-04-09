from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.application.services.auth_service import AuthService
from app.application.services.session_service import SessionService
from app.domain.schemas import PatientCreate, SessionCreate


def seed_therapist_and_session(db: Session) -> tuple[str, str]:
    auth = AuthService(db)
    therapist = auth.register_therapist(
        full_name="Test Therapist",
        email="test@example.com",
        password="secret123",
        google_account_email="test@clinic.com",
    )

    service = SessionService(db)
    session = service.create_session(
        SessionCreate(
            therapist_id=therapist.id,
            patient=PatientCreate(
                external_patient_id="PAT-001",
                first_name="Ana",
                last_name="Lopez",
                consent_reference="CONS-1",
                intake_id="INT-1",
                signed_form_id="FORM-1",
            ),
            google_meet_space_name="spaces/test",
            google_conference_record_name="conferenceRecords/test",
            session_started_at=datetime.now(UTC) - timedelta(hours=1),
            session_ended_at=datetime.now(UTC),
        )
    )

    db.commit()
    return therapist.id, session.id
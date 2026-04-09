"""Seed script for local demo data."""

from __future__ import annotations

from pathlib import Path
from sqlalchemy import select

from app.application.services.auth_service import AuthService
from app.application.services.demo_onboarding_service import DemoOnboardingService
from app.application.services.prompt_registry import PromptRegistry
from app.db.session import SessionLocal
from app.domain.models import Session as SessionModel, Therapist


DEMO_EMAIL = "demo@clinic.com"
LEGACY_DEMO_EMAIL = "demo@clinic.local"


def run() -> None:
    db = SessionLocal()
    try:
        auth = AuthService(db)
        therapist = db.scalar(
            select(Therapist).where(Therapist.email.in_([DEMO_EMAIL, LEGACY_DEMO_EMAIL]))
        )
        if therapist is None:
            therapist = auth.register_therapist(
                full_name="Dra. Laura Martinez",
                email=DEMO_EMAIL,
                password="demo1234",
                google_account_email="laura.martinez@clinic.com",
            )
        elif therapist.email != DEMO_EMAIL:
            therapist.email = DEMO_EMAIL
            therapist.google_account_email = "laura.martinez@clinic.com"
            db.add(therapist)

        templates_dir = Path(__file__).resolve().parents[2] / "assets" / "templates"
        default_docx = templates_dir / "plantilla_historia_clinica_respira_integral_editable_final.docx"
        default_pdf = templates_dir / "plantilla_historia_clinica_respira_integral_of.pdf"
        if default_docx.exists():
            therapist.template_docx_path = str(default_docx)
        if default_pdf.exists():
            therapist.template_pdf_path = str(default_pdf)
        db.add(therapist)

        registry = PromptRegistry(db)
        registry.ensure_seeded(["clinical_draft"])

        onboarding = DemoOnboardingService(db)
        created = onboarding.ensure_demo_sessions_for_therapist(therapist)

        sessions = db.scalars(
            select(SessionModel)
            .where(SessionModel.therapist_id == therapist.id)
            .order_by(SessionModel.created_at.desc())
        ).all()

        db.commit()
        print("Seed completed")
        print(f"Therapist email: {therapist.email}")
        print("Therapist password: demo1234")
        print(f"Total demo sessions: {len(sessions)}")
        if created:
            print(f"Created now: {len(created)}")
            print(f"Latest Session ID: {sessions[0].id}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()

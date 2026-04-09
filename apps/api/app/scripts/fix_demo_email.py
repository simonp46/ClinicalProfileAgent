"""Repair legacy demo therapist email without manual SQL."""

from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.domain.models import Therapist

DEMO_EMAIL = "demo@clinic.com"
LEGACY_DEMO_EMAIL = "demo@clinic.local"
DEMO_GOOGLE_EMAIL = "laura.martinez@clinic.com"
LEGACY_GOOGLE_EMAIL = "laura.martinez@clinic.local"


def run() -> None:
    db = SessionLocal()
    try:
        therapist = db.scalar(
            select(Therapist).where(Therapist.email.in_([DEMO_EMAIL, LEGACY_DEMO_EMAIL]))
        )

        if therapist is None:
            print("No se encontro usuario demo para corregir.")
            return

        changed = False
        if therapist.email == LEGACY_DEMO_EMAIL:
            therapist.email = DEMO_EMAIL
            changed = True

        if therapist.google_account_email == LEGACY_GOOGLE_EMAIL:
            therapist.google_account_email = DEMO_GOOGLE_EMAIL
            changed = True

        if changed:
            db.add(therapist)
            db.commit()
            print("Usuario demo corregido.")
            print(f"Nuevo email: {therapist.email}")
        else:
            print("Usuario demo ya estaba correcto.")
            print(f"Email actual: {therapist.email}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()

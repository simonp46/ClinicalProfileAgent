"""Add therapist profile/contact and asset fields.

Revision ID: 20260327_0004
Revises: 20260327_0003
Create Date: 2026-03-27 18:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260327_0004"
down_revision: str | None = "20260327_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("therapists", sa.Column("phone", sa.String(length=128), nullable=True))
    op.add_column("therapists", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.add_column("therapists", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("therapists", sa.Column("profession", sa.String(length=255), nullable=True))
    op.add_column("therapists", sa.Column("profile_photo_path", sa.String(length=1024), nullable=True))
    op.add_column("therapists", sa.Column("signature_image_path", sa.String(length=1024), nullable=True))
    op.add_column("therapists", sa.Column("template_pdf_path", sa.String(length=1024), nullable=True))
    op.add_column("therapists", sa.Column("template_docx_path", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("therapists", "template_docx_path")
    op.drop_column("therapists", "template_pdf_path")
    op.drop_column("therapists", "signature_image_path")
    op.drop_column("therapists", "profile_photo_path")
    op.drop_column("therapists", "profession")
    op.drop_column("therapists", "address")
    op.drop_column("therapists", "contact_email")
    op.drop_column("therapists", "phone")

"""Add PDF export fields for generated documents.

Revision ID: 20260326_0002
Revises: 20260325_0001
Create Date: 2026-03-26 11:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260326_0002"
down_revision: str | None = "20260325_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generated_documents", sa.Column("exported_pdf_path", sa.String(length=1024), nullable=True))
    op.add_column(
        "generated_documents",
        sa.Column("exported_pdf_mime_type", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generated_documents", "exported_pdf_mime_type")
    op.drop_column("generated_documents", "exported_pdf_path")

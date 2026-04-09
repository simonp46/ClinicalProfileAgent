"""Add city field to patients and therapists.

Revision ID: 20260330_0005
Revises: 20260327_0004
Create Date: 2026-03-30 16:50:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260330_0005"
down_revision: str | None = "20260327_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column.get("name") == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("patients", "city"):
        op.add_column("patients", sa.Column("city", sa.String(length=255), nullable=True))
    if not _has_column("therapists", "city"):
        op.add_column("therapists", sa.Column("city", sa.String(length=255), nullable=True))


def downgrade() -> None:
    if _has_column("therapists", "city"):
        op.drop_column("therapists", "city")
    if _has_column("patients", "city"):
        op.drop_column("patients", "city")


"""Add address and profession fields to patients.

Revision ID: 20260327_0003
Revises: 20260326_0002
Create Date: 2026-03-27 12:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260327_0003"
down_revision: str | None = "20260326_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("patients", sa.Column("profession", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "profession")
    op.drop_column("patients", "address")

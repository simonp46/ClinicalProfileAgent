"""add password reset codes

Revision ID: 20260409_0008
Revises: 20260407_0007
Create Date: 2026-04-09 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_0008"
down_revision = "20260407_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("therapist_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["therapist_id"], ["therapists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_password_reset_codes_therapist_id", "password_reset_codes", ["therapist_id"]
    )
    op.create_index("ix_password_reset_codes_email", "password_reset_codes", ["email"])
    op.create_index("ix_password_reset_codes_code_hash", "password_reset_codes", ["code_hash"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_codes_code_hash", table_name="password_reset_codes")
    op.drop_index("ix_password_reset_codes_email", table_name="password_reset_codes")
    op.drop_index("ix_password_reset_codes_therapist_id", table_name="password_reset_codes")
    op.drop_table("password_reset_codes")

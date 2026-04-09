"""add microsoft teams oauth support

Revision ID: 20260407_0007
Revises: 20260407_0006
Create Date: 2026-04-07 01:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0007"
down_revision = "20260407_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE sessionsource ADD VALUE IF NOT EXISTS 'microsoft_teams'")
    op.add_column("therapists", sa.Column("microsoft_account_email", sa.String(length=255), nullable=True))
    op.add_column("therapists", sa.Column("microsoft_oauth_subject", sa.String(length=255), nullable=True))
    op.add_column("therapists", sa.Column("microsoft_oauth_access_token", sa.String(length=4096), nullable=True))
    op.add_column("therapists", sa.Column("microsoft_oauth_refresh_token", sa.String(length=4096), nullable=True))
    op.add_column("therapists", sa.Column("microsoft_oauth_scopes", sa.String(length=2048), nullable=True))
    op.add_column("therapists", sa.Column("microsoft_oauth_token_expiry", sa.DateTime(timezone=True), nullable=True))
    op.add_column("therapists", sa.Column("microsoft_oauth_connected_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("therapists", "microsoft_oauth_connected_at")
    op.drop_column("therapists", "microsoft_oauth_token_expiry")
    op.drop_column("therapists", "microsoft_oauth_scopes")
    op.drop_column("therapists", "microsoft_oauth_refresh_token")
    op.drop_column("therapists", "microsoft_oauth_access_token")
    op.drop_column("therapists", "microsoft_oauth_subject")
    op.drop_column("therapists", "microsoft_account_email")

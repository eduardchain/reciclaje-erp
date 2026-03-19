"""Add per_kg to commission_type enum.

Revision ID: e1f2a3b4c5d6
Revises: b4c5d6e7f8a9
Create Date: 2026-03-19
"""
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE commission_type ADD VALUE IF NOT EXISTS 'per_kg'")


def downgrade():
    pass  # PostgreSQL no permite remover enum values

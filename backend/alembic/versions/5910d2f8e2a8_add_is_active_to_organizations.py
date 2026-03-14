"""add is_active to organizations

Revision ID: 5910d2f8e2a8
Revises: e8f9a0b1c2d3
Create Date: 2026-03-14 08:33:36.284837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5910d2f8e2a8'
down_revision: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar columna is_active a organizations."""
    op.add_column('organizations', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))


def downgrade() -> None:
    """Quitar columna is_active de organizations."""
    op.drop_column('organizations', 'is_active')

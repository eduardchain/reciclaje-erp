"""add investor_type to third_parties

Revision ID: b68f8a31ad8f
Revises: ba281361cb2c
Create Date: 2026-03-15 12:54:45.320904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b68f8a31ad8f'
down_revision: Union[str, Sequence[str], None] = 'ba281361cb2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('third_parties', sa.Column(
        'investor_type', sa.String(length=50), nullable=True,
        comment='socio, obligacion_financiera (solo para is_investor=True)',
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('third_parties', 'investor_type')

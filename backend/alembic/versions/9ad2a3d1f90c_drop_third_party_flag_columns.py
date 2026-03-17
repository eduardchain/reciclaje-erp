"""drop_third_party_flag_columns

Eliminar columnas de flags booleanos y campos relacionados de third_parties.
La unica fuente de verdad ahora es la tabla third_party_categories + assignments.

Revision ID: 9ad2a3d1f90c
Revises: 2a6eec48d012
Create Date: 2026-03-16 18:21:57.369541

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9ad2a3d1f90c'
down_revision: Union[str, Sequence[str], None] = '2a6eec48d012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop flag columns from third_parties."""
    op.drop_column('third_parties', 'is_supplier')
    op.drop_column('third_parties', 'is_customer')
    op.drop_column('third_parties', 'is_investor')
    op.drop_column('third_parties', 'is_provision')
    op.drop_column('third_parties', 'is_liability')
    op.drop_column('third_parties', 'investor_type')
    op.drop_column('third_parties', 'category')


def downgrade() -> None:
    """Restore flag columns to third_parties."""
    op.add_column('third_parties', sa.Column('category', sa.String(100), nullable=True))
    op.add_column('third_parties', sa.Column('investor_type', sa.String(50), nullable=True))
    op.add_column('third_parties', sa.Column('is_liability', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('third_parties', sa.Column('is_provision', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('third_parties', sa.Column('is_investor', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('third_parties', sa.Column('is_customer', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('third_parties', sa.Column('is_supplier', sa.Boolean(), nullable=False, server_default='false'))

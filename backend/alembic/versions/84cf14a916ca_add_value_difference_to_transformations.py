"""add_value_difference_to_transformations

Revision ID: 84cf14a916ca
Revises: 85e63348972d
Create Date: 2026-03-11 01:23:49.073855

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '84cf14a916ca'
down_revision: Union[str, Sequence[str], None] = '85e63348972d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar campo value_difference a material_transformations."""
    op.add_column(
        'material_transformations',
        sa.Column(
            'value_difference',
            sa.Numeric(precision=15, scale=2),
            nullable=True,
            comment='Diferencia de valorizacion: sum(destinos) - distributable_value. Positivo=ganancia, Negativo=perdida',
        ),
    )


def downgrade() -> None:
    """Quitar campo value_difference."""
    op.drop_column('material_transformations', 'value_difference')

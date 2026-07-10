"""cost_adjustment en inventory_adjustments y material_transformation_lines (Modelo L PR-4)

Revision ID: 7c2f9a41d8e3
Revises: 8548fcde95ee
Create Date: 2026-07-10 14:30:00.000000

Fase 2c del plan docs/planes/plan-fix-estructural-costo-promedio.md:
ajustes increase y destinos de transformacion adoptan el helper de
conservacion de valor. Escrita a mano (mismo criterio que 8548fcde95ee:
el autogenerate arrastra drift ajeno).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c2f9a41d8e3'
down_revision: Union[str, Sequence[str], None] = '8548fcde95ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'inventory_adjustments',
        sa.Column(
            'cost_adjustment',
            sa.Numeric(precision=15, scale=2),
            server_default='0',
            nullable=False,
            comment='Ajuste de costo por sobreventa (Modelo L #65, solo increase sobre '
                    'pool negativo): COGS ya cargado vs costo real de entrada. Entra al P&L.',
        ),
    )
    op.add_column(
        'material_transformation_lines',
        sa.Column(
            'cost_adjustment',
            sa.Numeric(precision=15, scale=2),
            server_default='0',
            nullable=False,
            comment='Ajuste de costo por sobreventa (Modelo L #65, destino sobre pool '
                    'negativo): COGS ya cargado vs costo real de entrada. Entra al P&L.',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('material_transformation_lines', 'cost_adjustment')
    op.drop_column('inventory_adjustments', 'cost_adjustment')

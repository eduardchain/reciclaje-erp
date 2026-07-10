"""cost_adjustment en purchase_lines y cancellation_cost_adjustment en sales (Modelo L PR-2)

Revision ID: 8548fcde95ee
Revises: 4d8f2c1e9a7b
Create Date: 2026-07-10 07:21:15.525427

Escrita a mano: el autogenerate arrastraba drift ajeno (drop de
backfill_liquidated_at_audit — tabla de rollback del backfill #43 que NO
se toca — y cientos de alter_column de comentarios). Solo las 2 columnas
del plan docs/planes/plan-fix-estructural-costo-promedio.md seccion 4.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8548fcde95ee'
down_revision: Union[str, Sequence[str], None] = '4d8f2c1e9a7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'purchase_lines',
        sa.Column(
            'cost_adjustment',
            sa.Numeric(precision=15, scale=2),
            server_default='0',
            nullable=False,
            comment='Ajuste de costo por sobreventa al liquidar (Modelo L #65): '
                    'diferencia entre el COGS ya cargado por el hueco negativo y el '
                    'costo real de reposicion. >0 ganancia, <0 perdida. Entra al P&L.',
        ),
    )
    op.add_column(
        'sales',
        sa.Column(
            'cancellation_cost_adjustment',
            sa.Numeric(precision=15, scale=2),
            server_default='0',
            nullable=False,
            comment='Ajuste de costo al cancelar venta liquidada sobre pool en hueco '
                    '(Modelo L #65). >0 ganancia, <0 perdida. Entra al P&L por cancelled_at.',
        ),
    )
    # Documentar el 5o source_type (sale_cancellation) en el comment de la columna
    op.alter_column(
        'material_cost_histories', 'source_type',
        existing_type=sa.VARCHAR(length=50),
        comment='purchase_liquidation | adjustment_increase | transformation_in | '
                'transformation_out | sale_cancellation',
        existing_comment='purchase_liquidation | adjustment_increase | transformation_in | transformation_out',
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'material_cost_histories', 'source_type',
        existing_type=sa.VARCHAR(length=50),
        comment='purchase_liquidation | adjustment_increase | transformation_in | transformation_out',
        existing_comment='purchase_liquidation | adjustment_increase | transformation_in | '
                         'transformation_out | sale_cancellation',
        existing_nullable=False,
    )
    op.drop_column('sales', 'cancellation_cost_adjustment')
    op.drop_column('purchase_lines', 'cost_adjustment')

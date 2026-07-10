"""Fase 5 remocion ponderada: columnas de ajuste por reversion

Revision ID: 4530b4e47938
Revises: 7c2f9a41d8e3
Create Date: 2026-07-10 18:00:00.000000

Plan docs/planes/plan-fase5-remocion-ponderada.md: las reversiones (cancelar
compra liquidada, anular ajuste, anular transformacion) dejan de rebobinar el
costo promedio via MaterialCostHistory y pasan a remocion/reingreso ponderado
con conservacion de valor. La diferencia se persiste en estas columnas y entra
al P&L por cancelled_at/annulled_at. server_default=0 -> el P&L historico NO
cambia al deploy. Escrita a mano (el autogenerate arrastra drift ajeno).
ID de revision ALEATORIO (leccion PR-4: los IDs hex secuenciales estan minados).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4530b4e47938'
down_revision: Union[str, Sequence[str], None] = '7c2f9a41d8e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'purchases',
        sa.Column(
            'cancellation_cost_adjustment',
            sa.Numeric(precision=15, scale=2),
            server_default='0',
            nullable=False,
            comment='Ajuste de costo al cancelar compra liquidada (Fase 5 remocion '
                    'ponderada): diferencia entre lo que la compra metio al pool y lo '
                    'que la remocion pudo sacar. Entra al P&L por cancelled_at.',
        ),
    )
    op.add_column(
        'inventory_adjustments',
        sa.Column(
            'annul_cost_adjustment',
            sa.Numeric(precision=15, scale=2),
            server_default='0',
            nullable=False,
            comment='Ajuste de costo al anular el ajuste (Fase 5 remocion/reingreso '
                    'ponderado). Entra al P&L por annulled_at aunque el ajuste este '
                    'annulled (es el efecto real de la anulacion).',
        ),
    )
    op.add_column(
        'material_transformations',
        sa.Column(
            'annul_cost_adjustment',
            sa.Numeric(precision=15, scale=2),
            server_default='0',
            nullable=False,
            comment='Ajuste de costo al anular la transformacion (Fase 5 remocion '
                    'ponderada de destinos + reingreso ponderado de fuente). Entra al '
                    'P&L por annulled_at aunque la transformacion este annulled.',
        ),
    )
    # MCH gana 3 source_types de reversion (append-only: las reversiones ya no
    # borran el registro original, escriben el suyo).
    op.alter_column(
        'material_cost_histories',
        'source_type',
        existing_type=sa.String(length=50),
        comment='purchase_liquidation | adjustment_increase | transformation_in | '
                'transformation_out | sale_cancellation | purchase_cancellation | '
                'adjustment_annulment | transformation_annulment',
        existing_comment='purchase_liquidation | adjustment_increase | transformation_in | '
                         'transformation_out | sale_cancellation',
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'material_cost_histories',
        'source_type',
        existing_type=sa.String(length=50),
        comment='purchase_liquidation | adjustment_increase | transformation_in | '
                'transformation_out | sale_cancellation',
        existing_comment='purchase_liquidation | adjustment_increase | transformation_in | '
                         'transformation_out | sale_cancellation | purchase_cancellation | '
                         'adjustment_annulment | transformation_annulment',
        existing_nullable=False,
    )
    op.drop_column('material_transformations', 'annul_cost_adjustment')
    op.drop_column('inventory_adjustments', 'annul_cost_adjustment')
    op.drop_column('purchases', 'cancellation_cost_adjustment')

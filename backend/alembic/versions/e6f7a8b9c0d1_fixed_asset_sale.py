"""Venta de activos fijos — 3 columnas sale_* en fixed_assets.

Plan docs/planes/plan-venta-activos-fijos.md (v1.0 QA-GO). La venta da de
baja el valor en libros contra el precio (D1: SIN depreciacion acelerada,
current_value queda congelado) y la diferencia precio - libro es la linea
P&L "Ganancia/Perdida por Venta de Activos", gobernada por el status del
MM enlazado (patron oversell #65/#66).

Aditiva y nullable, sin backfill: la linea P&L suma 0 para datos
existentes y ningun corte historico se re-presenta (golden intacto).

Revision ID: e6f7a8b9c0d1
Revises: c4d5e6f7a8b9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fixed_assets",
        sa.Column(
            "sale_price",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Precio de la ultima venta (NULL = nunca vendido)",
        ),
    )
    op.add_column(
        "fixed_assets",
        sa.Column(
            "sale_gain",
            sa.Numeric(15, 2),
            nullable=True,
            comment=(
                "sale_price - current_value al momento de la venta (signed; "
                "cuenta en P&L solo si el MM enlazado esta confirmed)"
            ),
        ),
    )
    op.add_column(
        "fixed_assets",
        sa.Column("sale_movement_id", GUID(), nullable=True),
    )
    op.create_foreign_key(
        None,
        "fixed_assets",
        "money_movements",
        ["sale_movement_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_column("fixed_assets", "sale_movement_id")
    op.drop_column("fixed_assets", "sale_gain")
    op.drop_column("fixed_assets", "sale_price")

"""Cargos de operacion: charge_type en comisiones de compra y venta (plan bonos-fletes)

Generaliza el mecanismo de comisiones (#30 compras, #23 ventas) a cargos:
- purchase_commissions.charge_type: commission | freight
- sale_commissions.charge_type: commission | freight | bonus

server_default='commission' → todas las comisiones historicas quedan
correctamente tipadas sin backfill. String validado en servicio/schema
(Literal), NO enum de Postgres — charge_type (que ES) es ortogonal a
commission_type (como se calcula).

Revision ID: c45cbce9f391
Revises: 038bdae40eb3
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c45cbce9f391"
down_revision = "038bdae40eb3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_commissions",
        sa.Column("charge_type", sa.String(20), nullable=False, server_default="commission"),
    )
    op.add_column(
        "sale_commissions",
        sa.Column("charge_type", sa.String(20), nullable=False, server_default="commission"),
    )


def downgrade() -> None:
    op.drop_column("sale_commissions", "charge_type")
    op.drop_column("purchase_commissions", "charge_type")

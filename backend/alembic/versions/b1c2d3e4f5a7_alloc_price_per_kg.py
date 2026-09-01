"""Modo de liquidacion por kg en el reparto de la Entrada (correccion Q-15).

Dos columnas nullable en inbound_line_allocations — tabla EXCLUSIVA SAC (cero
filas en las 3 orgs cliente), asi que el golden no aplica.

NULL en ambas = la asignacion se digito por unitario o por total, o sea el
comportamiento previo byte a byte.

Revision ID: b1c2d3e4f5a7
Revises: a5b6c7d8e9f0
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a7"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inbound_line_allocations",
        sa.Column("price_per_kg", sa.Numeric(15, 2), nullable=True),
    )
    op.add_column(
        "inbound_line_allocations",
        sa.Column("weight_kg_used", sa.Numeric(15, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inbound_line_allocations", "weight_kg_used")
    op.drop_column("inbound_line_allocations", "price_per_kg")

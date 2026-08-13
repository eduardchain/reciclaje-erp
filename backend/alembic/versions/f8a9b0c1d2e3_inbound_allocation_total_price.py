"""Ciclo Entradas (Q-15): valor total digitado por asignacion

Hugo, reunion 12-ago: al liquidar, Johana puede digitar el VALOR TOTAL de la
asignacion en vez del precio unitario — "el precio unitario seria una formula,
costo total dividido unidades".

Se PERSISTE en vez de solo derivarse porque #93 D20 promete que el reparto
sobrevive el round-trip de desliquidar/re-liquidar: un modo de captura que no
sobrevive es un reparto que en realidad no se conservo (el operador vuelve a
la pantalla y ve otra cosa de la que guardo).

Aditiva y nullable, sin backfill: NULL = se digito el precio unitario, que es
el comportamiento de siempre. `inbound_line_allocations` es tabla EXCLUSIVA de
SAC (cero filas en las 3 orgs cliente) -> sin golden gate.

Revision ID: f8a9b0c1d2e3
Revises: f1a2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa


revision = "f8a9b0c1d2e3"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inbound_line_allocations",
        sa.Column(
            "total_price",
            sa.Numeric(15, 2),
            nullable=True,
            comment="Valor total digitado (Q-15). NULL = se digito el unit_price",
        ),
    )


def downgrade() -> None:
    op.drop_column("inbound_line_allocations", "total_price")

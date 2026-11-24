"""SAC: factor de Willard escogido en cada linea de la Entrada

Plan: docs/planes/plan-sac-factor-willard.md v1.3, D3 y §5.

`inbound_order_lines.conversion_option` (String(40), NULL). NULL = el factor por
defecto de la formula vigente (`lead_percentage`), que es lo que tienen todas
las lineas existentes: sin backfill. `inbound_order_lines` es tabla exclusiva
de SAC (flag `kg_ledger_enabled`).

Aditiva pura. Downgrade: borra la columna; las lineas liquidadas con una
alternativa conservan sus kilos (viven en el libro kg con su snapshot), pero
pierden el nombre del factor en la linea.

Revision ID: f8b0c2d4e6a9
Revises: e7f9a1b3c5d8
"""
from alembic import op
import sqlalchemy as sa

revision = "f8b0c2d4e6a9"
down_revision = "e7f9a1b3c5d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inbound_order_lines",
        sa.Column(
            "conversion_option",
            sa.String(length=40),
            nullable=True,
            comment="Factor de Willard escogido (nombre de la alternativa); NULL = el defecto",
        ),
    )


def downgrade() -> None:
    op.drop_column("inbound_order_lines", "conversion_option")

"""SAC Ciclo B addendum — nota informativa de cabecera en inbound_orders.

Feedback de pruebas de Daniel (2026-07-17): la captura en patio necesita una
nota libre (junto al quick-create de conductor/vehiculo). Aditiva nullable —
inbound_orders aun no existe en prod (deploya en el mismo tren), golden intacto.

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inbound_orders",
        sa.Column(
            "notes",
            sa.String(length=1000),
            nullable=True,
            comment="Nota informativa de la captura en patio",
        ),
    )


def downgrade() -> None:
    op.drop_column("inbound_orders", "notes")

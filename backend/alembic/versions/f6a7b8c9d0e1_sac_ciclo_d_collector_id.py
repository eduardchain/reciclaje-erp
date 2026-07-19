"""SAC Ciclo D — recolector en la entrada (collector_id).

Decision de producto (Daniel 2026-07-17): la comision del recolector (Green
Loop) NO se prorratea al costo del material (#30) — se causa como GASTO
(expense_accrual con categoria sistema) al liquidar la compra derivada, SOLO
en compras regulares (Q-02 Johana: nunca en willard).

Aditiva nullable sobre tabla SAC-only (router flag-gated) — cero exposicion
prod, golden intacto. El MM de la comision usa columnas E2 ya existentes
(source_type/source_id/tariff_id/warehouse_id): cero migracion en tesoreria.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.base import GUID

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inbound_orders",
        sa.Column(
            "collector_id",
            GUID(),
            nullable=True,
            comment="Recolector por comision (service_provider) — solo tipo purchase; la comision se causa como gasto al liquidar",
        ),
    )
    op.create_foreign_key(
        None,  # default de PG = paridad con create_all (baseline parity check)
        "inbound_orders",
        "third_parties",
        ["collector_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "inbound_orders_collector_id_fkey", "inbound_orders", type_="foreignkey"
    )
    op.drop_column("inbound_orders", "collector_id")

"""add status to profit_distributions for annulment

Revision ID: 9cff249f95cf
Revises: 3acfc5ab3d68
Create Date: 2026-05-17 11:56:33.244776

Anular una `ProfitDistribution` requiere persistir el estado en la entidad
agregada — no alcanza con que sus `MoneyMovement` hijos esten anulados
(la distribucion seguia apareciendo en el historial y contando en
`calculate_distributed_profit`). Esta migracion:

1. Agrega columnas status / annulled_reason / annulled_at / annulled_by.
2. Backfill: marca como `annulled` aquellas distribuciones cuyas lineas
   tengan TODAS un MoneyMovement anulado (o sin MM asociado). El reason
   queda como 'Backfill: MoneyMovements ya anulados'.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9cff249f95cf'
down_revision: Union[str, Sequence[str], None] = '3acfc5ab3d68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profit_distributions",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="confirmed"),
    )
    op.add_column(
        "profit_distributions",
        sa.Column("annulled_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "profit_distributions",
        sa.Column("annulled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "profit_distributions",
        sa.Column("annulled_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_profit_distributions_annulled_by_users",
        "profit_distributions",
        "users",
        ["annulled_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # Backfill: distribuciones con TODAS sus lineas con MM anulado/NULL -> annulled
    op.execute(
        """
        UPDATE profit_distributions p
        SET status = 'annulled',
            annulled_reason = 'Backfill: MoneyMovements ya anulados',
            annulled_at = NOW()
        WHERE NOT EXISTS (
            SELECT 1
            FROM profit_distribution_lines l
            LEFT JOIN money_movements mm ON mm.id = l.money_movement_id
            WHERE l.distribution_id = p.id
              AND mm.id IS NOT NULL
              AND mm.status = 'confirmed'
        )
        AND EXISTS (
            SELECT 1 FROM profit_distribution_lines l WHERE l.distribution_id = p.id
        );
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_profit_distributions_annulled_by_users",
        "profit_distributions",
        type_="foreignkey",
    )
    op.drop_column("profit_distributions", "annulled_by")
    op.drop_column("profit_distributions", "annulled_at")
    op.drop_column("profit_distributions", "annulled_reason")
    op.drop_column("profit_distributions", "status")

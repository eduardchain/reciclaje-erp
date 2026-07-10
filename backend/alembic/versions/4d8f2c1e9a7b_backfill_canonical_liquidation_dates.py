"""Backfill fechas canonicas de liquidacion (incidente balance historico)

1. MaterialCostHistory.transaction_date de purchase_liquidation → liquidated_at
   de su compra (antes: fecha del documento). Sin esto, liquidar tarde una
   compra vieja reescribia el costo promedio de cortes historicos anteriores.
2. MoneyMovement.date de commission_accrual → liquidated_at de su venta
   (antes: fecha del documento). Sin esto, liquidar tarde una venta con
   comision reescribia el saldo historico del comisionista y el P&L ponia
   la comision en un mes distinto al de su revenue.

Ambas idempotentes (WHERE excluye filas ya alineadas) y reversibles
(downgrade re-deriva de la fecha del documento).

Dimensionado en replica prod 2026-07-08: Costa 160 accruals desalineados
(53 cruzan de mes en P&L); Meta y Demo 0. MCH: solo compras liquidadas con
liquidation_date distinta al documento (311 compras en Costa).

Revision ID: 4d8f2c1e9a7b
Revises: f0a7d1e3dd07
Create Date: 2026-07-08
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "4d8f2c1e9a7b"
down_revision = "f0a7d1e3dd07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. MCH de liquidacion de compra → fecha de liquidacion de la compra
    op.execute(
        """
        UPDATE material_cost_histories mch
        SET transaction_date = (p.liquidated_at AT TIME ZONE 'UTC')::date
        FROM purchases p
        WHERE mch.source_type = 'purchase_liquidation'
          AND mch.source_id = p.id
          AND p.liquidated_at IS NOT NULL
          AND mch.transaction_date IS DISTINCT FROM (p.liquidated_at AT TIME ZONE 'UTC')::date
        """
    )

    # 2. commission_accrual → fecha de liquidacion de su venta
    #    (todas los status: los anulados no cuentan en reportes pero quedan coherentes)
    op.execute(
        """
        UPDATE money_movements mm
        SET date = s.liquidated_at
        FROM sales s
        WHERE mm.movement_type = 'commission_accrual'
          AND mm.sale_id = s.id
          AND s.liquidated_at IS NOT NULL
          AND mm.date IS DISTINCT FROM s.liquidated_at
        """
    )


def downgrade() -> None:
    # Re-derivar de la fecha del documento (comportamiento previo)
    op.execute(
        """
        UPDATE material_cost_histories mch
        SET transaction_date = (p.date AT TIME ZONE 'UTC')::date
        FROM purchases p
        WHERE mch.source_type = 'purchase_liquidation'
          AND mch.source_id = p.id
          AND mch.transaction_date IS DISTINCT FROM (p.date AT TIME ZONE 'UTC')::date
        """
    )
    op.execute(
        """
        UPDATE money_movements mm
        SET date = s.date
        FROM sales s
        WHERE mm.movement_type = 'commission_accrual'
          AND mm.sale_id = s.id
          AND mm.date IS DISTINCT FROM s.date
        """
    )

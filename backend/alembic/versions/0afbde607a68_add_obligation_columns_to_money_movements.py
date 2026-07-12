"""Vinculo obligacion en money_movements + indice parcial de idempotencia (plan F)

- financial_obligation_id: FK a la obligacion (tipos obligation_* / loan_*),
  mismo patron que sale_id/purchase_id pero RESTRICT (una obligacion con
  movimientos no se borra).
- obligation_period: "YYYY-MM" SOLO en causaciones de interes.
- uq_obligation_accrual_period: 1 causacion CONFIRMADA por (obligacion, periodo)
  — espejo del uq_asset_depreciation_period, pero parcial: anular libera el
  slot para recausar.

Revision ID: 0afbde607a68
Revises: 2df40742789a
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0afbde607a68'
down_revision = '2df40742789a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'money_movements',
        sa.Column('financial_obligation_id', sa.UUID(), nullable=True,
                  comment='Obligacion financiera vinculada (tipos obligation_* / loan_*)'),
    )
    op.add_column(
        'money_movements',
        sa.Column('obligation_period', sa.String(length=7), nullable=True,
                  comment='"YYYY-MM" causado — SOLO causaciones de interes (indice parcial de idempotencia)'),
    )
    op.create_foreign_key(
        'fk_money_movements_financial_obligation_id',
        'money_movements', 'financial_obligations',
        ['financial_obligation_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_index(
        'ix_money_movements_financial_obligation_id', 'money_movements',
        ['financial_obligation_id'], unique=False,
    )
    op.create_index(
        'uq_obligation_accrual_period', 'money_movements',
        ['financial_obligation_id', 'obligation_period'],
        unique=True,
        postgresql_where=sa.text(
            "movement_type IN ('obligation_interest_accrual', 'loan_interest_accrual') "
            "AND status = 'confirmed'"
        ),
    )


def downgrade() -> None:
    op.drop_index('uq_obligation_accrual_period', table_name='money_movements')
    op.drop_index('ix_money_movements_financial_obligation_id', table_name='money_movements')
    op.drop_constraint('fk_money_movements_financial_obligation_id', 'money_movements', type_='foreignkey')
    op.drop_column('money_movements', 'obligation_period')
    op.drop_column('money_movements', 'financial_obligation_id')

"""Obligaciones financieras bidireccionales: tabla financial_obligations (plan F)

Prestamos por pagar (nos prestaron) y por cobrar (prestamos nosotros).
Interes simple 30/360 sobre capital vigente, causacion mensual por batch manual.
1 tercero = 1 obligacion activa (validacion en service). Los 8 movement types
nuevos no requieren migracion (columna String) — ver migracion siguiente para
las columnas de vinculo en money_movements.

Revision ID: 2df40742789a
Revises: 8d1a27b7bb31
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2df40742789a'
down_revision = '8d1a27b7bb31'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'financial_obligations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('third_party_id', sa.UUID(), nullable=False,
                  comment='1 obligacion ACTIVA por tercero (validacion en service)'),
        sa.Column('direction', sa.String(length=10), nullable=False,
                  comment='payable = nos prestaron | receivable = prestamos nosotros'),
        sa.Column('monthly_rate', sa.Numeric(precision=5, scale=2), nullable=False,
                  comment='% mensual fijo de por vida (2.00 = 2%)'),
        sa.Column('capital_balance', sa.Numeric(precision=15, scale=2), nullable=False,
                  server_default='0', comment='Capital vigente'),
        sa.Column('pending_interest', sa.Numeric(precision=15, scale=2), nullable=False,
                  server_default='0',
                  comment='Intereses causados sin pagar/cobrar (congelados, no capitalizan)'),
        sa.Column('accrual_start_period', sa.String(length=7), nullable=False,
                  comment='"YYYY-MM": primer mes que causa el modulo (corte anti doble conteo)'),
        sa.Column('last_accrued_period', sa.String(length=7), nullable=True,
                  comment='"YYYY-MM": ultimo mes causado — guard retroactivo + cursor del batch'),
        sa.Column('disbursement_date', sa.DateTime(timezone=True), nullable=True,
                  comment='Fecha del desembolso inicial (NULL si nacio por migracion de saldo)'),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='active',
                  comment='active | settled (cierre manual con capital y pendientes en 0)'),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['third_party_id'], ['third_parties.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_financial_obligations_organization_id', 'financial_obligations',
        ['organization_id'], unique=False,
    )
    op.create_index(
        'ix_financial_obligations_third_party_id', 'financial_obligations',
        ['third_party_id'], unique=False,
    )
    op.create_index(
        'ix_financial_obligations_status', 'financial_obligations',
        ['status'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_financial_obligations_status', table_name='financial_obligations')
    op.drop_index('ix_financial_obligations_third_party_id', table_name='financial_obligations')
    op.drop_index('ix_financial_obligations_organization_id', table_name='financial_obligations')
    op.drop_table('financial_obligations')

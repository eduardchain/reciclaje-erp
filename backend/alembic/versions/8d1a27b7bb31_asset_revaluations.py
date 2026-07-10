"""Revalorizacion de activos fijos: tabla asset_revaluations (requerimiento D Costa)

La contrapartida de una revalorizacion SIEMPRE es una cuenta o un tercero
(mejora capitalizable / recuperacion de valor) — cero P&L, cero patrimonio.
Los 4 tipos nuevos de MoneyMovement (asset_revaluation_payment/credit,
asset_devaluation_collection/receivable) no requieren migracion (columna String).

Revision ID: 8d1a27b7bb31
Revises: 4530b4e47938
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d1a27b7bb31'
down_revision = '4530b4e47938'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'asset_revaluations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('fixed_asset_id', sa.UUID(), nullable=False),
        sa.Column('revaluation_type', sa.String(length=10), nullable=False,
                  comment='increase | decrease'),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False,
                  comment='Siempre > 0; el signo lo da revaluation_type'),
        sa.Column('months_extended', sa.Integer(), nullable=False, server_default='0',
                  comment='Meses de vida util agregados (solo increase)'),
        sa.Column('value_before', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('value_after', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('monthly_before', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('monthly_after', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('period', sa.String(length=10), nullable=False,
                  comment='"YYYY-MM" derivado de la fecha de aplicacion (hoy Bogota) — ancla contable as-of'),
        sa.Column('money_movement_id', sa.UUID(), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False,
                  comment='Tiebreaker dentro del mismo period en el merge as-of'),
        sa.Column('applied_by', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('annulled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('annulled_by', sa.UUID(), nullable=True),
        sa.Column('annulled_reason', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fixed_asset_id'], ['fixed_assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['money_movement_id'], ['money_movements.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['applied_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['annulled_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_asset_revaluations_fixed_asset_id', 'asset_revaluations',
        ['fixed_asset_id'], unique=False,
    )
    op.create_index(
        'ix_asset_revaluations_organization_id', 'asset_revaluations',
        ['organization_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_asset_revaluations_organization_id', table_name='asset_revaluations')
    op.drop_index('ix_asset_revaluations_fixed_asset_id', table_name='asset_revaluations')
    op.drop_table('asset_revaluations')

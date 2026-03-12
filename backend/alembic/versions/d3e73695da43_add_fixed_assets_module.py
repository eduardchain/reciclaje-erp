"""add fixed assets module

Revision ID: d3e73695da43
Revises: c331bd643694
Create Date: 2026-03-12 13:55:44.035168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.base

# revision identifiers, used by Alembic.
revision: str = 'd3e73695da43'
down_revision: Union[str, Sequence[str], None] = 'c331bd643694'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tablas fixed_assets y asset_depreciations."""
    op.create_table('fixed_assets',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('asset_code', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('depreciation_start_date', sa.Date(), nullable=False),
        sa.Column('purchase_value', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('salvage_value', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('current_value', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('accumulated_depreciation', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('depreciation_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('monthly_depreciation', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('useful_life_months', sa.Integer(), nullable=False),
        sa.Column('expense_category_id', app.models.base.GUID(), nullable=False),
        sa.Column('third_party_id', app.models.base.GUID(), nullable=True),
        sa.Column('purchase_movement_id', app.models.base.GUID(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('disposed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disposed_by', app.models.base.GUID(), nullable=True),
        sa.Column('disposal_reason', sa.String(length=500), nullable=True),
        sa.Column('created_by', app.models.base.GUID(), nullable=True),
        sa.Column('organization_id', app.models.base.GUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['disposed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['expense_category_id'], ['expense_categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_movement_id'], ['money_movements.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['third_party_id'], ['third_parties.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fixed_assets_org_status', 'fixed_assets', ['organization_id', 'status'], unique=False)
    op.create_index(op.f('ix_fixed_assets_organization_id'), 'fixed_assets', ['organization_id'], unique=False)

    op.create_table('asset_depreciations',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('fixed_asset_id', app.models.base.GUID(), nullable=False),
        sa.Column('depreciation_number', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('accumulated_after', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('current_value_after', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('money_movement_id', app.models.base.GUID(), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('applied_by', app.models.base.GUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['applied_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['fixed_asset_id'], ['fixed_assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['money_movement_id'], ['money_movements.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fixed_asset_id', 'period', name='uq_asset_depreciation_period'),
    )
    op.create_index(op.f('ix_asset_depreciations_fixed_asset_id'), 'asset_depreciations', ['fixed_asset_id'], unique=False)


def downgrade() -> None:
    """Eliminar tablas fixed_assets y asset_depreciations."""
    op.drop_index(op.f('ix_asset_depreciations_fixed_asset_id'), table_name='asset_depreciations')
    op.drop_table('asset_depreciations')
    op.drop_index(op.f('ix_fixed_assets_organization_id'), table_name='fixed_assets')
    op.drop_index('ix_fixed_assets_org_status', table_name='fixed_assets')
    op.drop_table('fixed_assets')

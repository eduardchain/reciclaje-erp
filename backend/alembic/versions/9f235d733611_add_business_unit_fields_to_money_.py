"""add business_unit fields to money_movements fixed_assets scheduled_expenses

Revision ID: 9f235d733611
Revises: f9a1b2c3d4e5
Create Date: 2026-03-17

Agrega campos de asignacion a Unidad de Negocio:
- business_unit_id (UUID FK nullable) — asignacion directa a 1 UN
- applicable_business_unit_ids (JSONB nullable) — prorrateo compartido entre UNs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '9f235d733611'
down_revision: Union[str, Sequence[str], None] = 'f9a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # money_movements
    op.add_column('money_movements', sa.Column('business_unit_id', sa.UUID(), nullable=True))
    op.add_column('money_movements', sa.Column('applicable_business_unit_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index('ix_money_movements_business_unit_id', 'money_movements', ['business_unit_id'])
    op.create_foreign_key('fk_money_movements_business_unit', 'money_movements', 'business_units', ['business_unit_id'], ['id'], ondelete='SET NULL')

    # fixed_assets
    op.add_column('fixed_assets', sa.Column('business_unit_id', sa.UUID(), nullable=True))
    op.add_column('fixed_assets', sa.Column('applicable_business_unit_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key('fk_fixed_assets_business_unit', 'fixed_assets', 'business_units', ['business_unit_id'], ['id'], ondelete='SET NULL')

    # scheduled_expenses
    op.add_column('scheduled_expenses', sa.Column('business_unit_id', sa.UUID(), nullable=True))
    op.add_column('scheduled_expenses', sa.Column('applicable_business_unit_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key('fk_scheduled_expenses_business_unit', 'scheduled_expenses', 'business_units', ['business_unit_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # scheduled_expenses
    op.drop_constraint('fk_scheduled_expenses_business_unit', 'scheduled_expenses', type_='foreignkey')
    op.drop_column('scheduled_expenses', 'applicable_business_unit_ids')
    op.drop_column('scheduled_expenses', 'business_unit_id')

    # fixed_assets
    op.drop_constraint('fk_fixed_assets_business_unit', 'fixed_assets', type_='foreignkey')
    op.drop_column('fixed_assets', 'applicable_business_unit_ids')
    op.drop_column('fixed_assets', 'business_unit_id')

    # money_movements
    op.drop_constraint('fk_money_movements_business_unit', 'money_movements', type_='foreignkey')
    op.drop_index('ix_money_movements_business_unit_id', 'money_movements')
    op.drop_column('money_movements', 'applicable_business_unit_ids')
    op.drop_column('money_movements', 'business_unit_id')

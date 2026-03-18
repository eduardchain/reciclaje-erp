"""add default business unit fields to expense_categories

Revision ID: a3b4c5d6e7f8
Revises: 9f235d733611
Create Date: 2026-03-18

Agrega campos de asignacion default de UN a categorias de gasto.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = '9f235d733611'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('expense_categories', sa.Column('default_business_unit_id', sa.UUID(), nullable=True))
    op.add_column('expense_categories', sa.Column('default_applicable_business_unit_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key('fk_expense_categories_default_bu', 'expense_categories', 'business_units', ['default_business_unit_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_expense_categories_default_bu', 'expense_categories', type_='foreignkey')
    op.drop_column('expense_categories', 'default_applicable_business_unit_ids')
    op.drop_column('expense_categories', 'default_business_unit_id')

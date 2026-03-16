"""add_parent_id_to_expense_categories

Revision ID: 9de734fc85be
Revises: a1b2c3d4e5f7
Create Date: 2026-03-16 12:44:16.681666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.base

# revision identifiers, used by Alembic.
revision: str = '9de734fc85be'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar parent_id a expense_categories para subcategorias (max 2 niveles)."""
    op.add_column('expense_categories', sa.Column(
        'parent_id', app.models.base.GUID(), nullable=True,
        comment='ID de la categoria padre (max 2 niveles).',
    ))
    op.create_index('ix_expense_categories_parent_id', 'expense_categories', ['parent_id'])
    op.create_foreign_key(
        'fk_expense_categories_parent_id',
        'expense_categories', 'expense_categories',
        ['parent_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Remover parent_id de expense_categories."""
    op.drop_constraint('fk_expense_categories_parent_id', 'expense_categories', type_='foreignkey')
    op.drop_index('ix_expense_categories_parent_id', table_name='expense_categories')
    op.drop_column('expense_categories', 'parent_id')

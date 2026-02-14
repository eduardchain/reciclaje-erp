"""agregar_tabla_expense_categories

Revision ID: 05dbf78c0530
Revises: 875a5bfaf460
Create Date: 2026-02-14 16:49:55.145929

Tabla para clasificar gastos en directos (afectan costo de material)
e indirectos (gastos administrativos). Necesaria para el modulo de tesoreria.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.models.base import GUID


# revision identifiers, used by Alembic.
revision: str = '05dbf78c0530'
down_revision: Union[str, Sequence[str], None] = '875a5bfaf460'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tabla expense_categories."""
    op.create_table('expense_categories',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_direct_expense', sa.Boolean(), nullable=False,
                   comment='True = gasto directo (afecta costo material). False = gasto indirecto (administrativo).'),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', GUID(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_expense_categories_name'), 'expense_categories', ['name'], unique=False)
    op.create_index(op.f('ix_expense_categories_organization_id'), 'expense_categories', ['organization_id'], unique=False)


def downgrade() -> None:
    """Eliminar tabla expense_categories."""
    op.drop_index(op.f('ix_expense_categories_organization_id'), table_name='expense_categories')
    op.drop_index(op.f('ix_expense_categories_name'), table_name='expense_categories')
    op.drop_table('expense_categories')

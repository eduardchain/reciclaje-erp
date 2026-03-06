"""create material_cost_histories table

Revision ID: a5f4ebedb73e
Revises: a8c3f2d19b45
Create Date: 2026-03-06 12:07:51.439205

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a5f4ebedb73e'
down_revision: Union[str, Sequence[str], None] = 'a8c3f2d19b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tabla de historial de costo de materiales."""
    op.create_table('material_cost_histories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('material_id', sa.Uuid(), nullable=False),
        sa.Column('previous_cost', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('new_cost', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('previous_stock', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('new_stock', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mch_org_material', 'material_cost_histories', ['organization_id', 'material_id'], unique=False)
    op.create_index('ix_mch_source', 'material_cost_histories', ['source_type', 'source_id'], unique=False)


def downgrade() -> None:
    """Eliminar tabla de historial de costo de materiales."""
    op.drop_index('ix_mch_source', table_name='material_cost_histories')
    op.drop_index('ix_mch_org_material', table_name='material_cost_histories')
    op.drop_table('material_cost_histories')

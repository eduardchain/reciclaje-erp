"""create_third_party_categories

Revision ID: 2a6eec48d012
Revises: 9de734fc85be
Create Date: 2026-03-16 14:54:33.530042

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.base

# revision identifiers, used by Alembic.
revision: str = '2a6eec48d012'
down_revision: Union[str, Sequence[str], None] = '9de734fc85be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tablas third_party_categories y third_party_category_assignments."""
    op.create_table('third_party_categories',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('parent_id', app.models.base.GUID(), nullable=True, comment='ID de la categoria padre (max 2 niveles).'),
        sa.Column('behavior_type', sa.String(length=50), nullable=True, comment='Tipo de comportamiento. Obligatorio en nivel 1, heredado en nivel 2.'),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', app.models.base.GUID(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['third_party_categories.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_third_party_categories_behavior_type'), 'third_party_categories', ['behavior_type'], unique=False)
    op.create_index(op.f('ix_third_party_categories_name'), 'third_party_categories', ['name'], unique=False)
    op.create_index(op.f('ix_third_party_categories_organization_id'), 'third_party_categories', ['organization_id'], unique=False)
    op.create_index(op.f('ix_third_party_categories_parent_id'), 'third_party_categories', ['parent_id'], unique=False)

    op.create_table('third_party_category_assignments',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('third_party_id', app.models.base.GUID(), nullable=False),
        sa.Column('category_id', app.models.base.GUID(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['third_party_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['third_party_id'], ['third_parties.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('third_party_id', 'category_id', name='uq_tp_category_assignment')
    )
    op.create_index(op.f('ix_third_party_category_assignments_category_id'), 'third_party_category_assignments', ['category_id'], unique=False)
    op.create_index(op.f('ix_third_party_category_assignments_third_party_id'), 'third_party_category_assignments', ['third_party_id'], unique=False)


def downgrade() -> None:
    """Eliminar tablas third_party_category_assignments y third_party_categories."""
    op.drop_index(op.f('ix_third_party_category_assignments_third_party_id'), table_name='third_party_category_assignments')
    op.drop_index(op.f('ix_third_party_category_assignments_category_id'), table_name='third_party_category_assignments')
    op.drop_table('third_party_category_assignments')
    op.drop_index(op.f('ix_third_party_categories_parent_id'), table_name='third_party_categories')
    op.drop_index(op.f('ix_third_party_categories_organization_id'), table_name='third_party_categories')
    op.drop_index(op.f('ix_third_party_categories_name'), table_name='third_party_categories')
    op.drop_index(op.f('ix_third_party_categories_behavior_type'), table_name='third_party_categories')
    op.drop_table('third_party_categories')

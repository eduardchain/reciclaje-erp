"""add profit_distribution tables

Revision ID: d6d507c083c7
Revises: b68f8a31ad8f
Create Date: 2026-03-15 23:43:54.755554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.base

# revision identifiers, used by Alembic.
revision: str = 'd6d507c083c7'
down_revision: Union[str, Sequence[str], None] = 'b68f8a31ad8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tablas profit_distributions y profit_distribution_lines."""
    op.create_table('profit_distributions',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', app.models.base.GUID(), nullable=True),
        sa.Column('organization_id', app.models.base.GUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_profit_distributions_organization_id'), 'profit_distributions', ['organization_id'], unique=False)

    op.create_table('profit_distribution_lines',
        sa.Column('id', app.models.base.GUID(), nullable=False),
        sa.Column('distribution_id', app.models.base.GUID(), nullable=False),
        sa.Column('third_party_id', app.models.base.GUID(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('money_movement_id', app.models.base.GUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['distribution_id'], ['profit_distributions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['money_movement_id'], ['money_movements.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['third_party_id'], ['third_parties.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Eliminar tablas de repartición de utilidades."""
    op.drop_table('profit_distribution_lines')
    op.drop_index(op.f('ix_profit_distributions_organization_id'), table_name='profit_distributions')
    op.drop_table('profit_distributions')

"""add purchase commissions table

Revision ID: ba281361cb2c
Revises: 5910d2f8e2a8
Create Date: 2026-03-14 12:21:22.149319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ba281361cb2c'
down_revision: Union[str, Sequence[str], None] = '5910d2f8e2a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crear tabla purchase_commissions."""
    op.create_table('purchase_commissions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('purchase_id', sa.UUID(), nullable=False),
        sa.Column('third_party_id', sa.UUID(), nullable=False, comment='Comisionista que recibe la comision'),
        sa.Column('concept', sa.String(length=255), nullable=False, comment='Descripcion de la comision'),
        sa.Column('commission_type', postgresql.ENUM('percentage', 'fixed', name='commission_type', create_type=False), nullable=False, comment='percentage (del total de compra) o fixed'),
        sa.Column('commission_value', sa.Numeric(precision=15, scale=2), nullable=False, comment='Porcentaje (0-100) o monto fijo'),
        sa.Column('commission_amount', sa.Numeric(precision=15, scale=2), nullable=False, comment='Monto calculado de la comision'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['third_party_id'], ['third_parties.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_purchase_commissions_purchase_id', 'purchase_commissions', ['purchase_id'])
    op.create_index('ix_purchase_commissions_third_party_id', 'purchase_commissions', ['third_party_id'])


def downgrade() -> None:
    """Eliminar tabla purchase_commissions."""
    op.drop_index('ix_purchase_commissions_third_party_id', table_name='purchase_commissions')
    op.drop_index('ix_purchase_commissions_purchase_id', table_name='purchase_commissions')
    op.drop_table('purchase_commissions')

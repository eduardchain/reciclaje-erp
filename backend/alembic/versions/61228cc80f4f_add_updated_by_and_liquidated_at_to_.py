"""add updated_by and liquidated_at to sales

Revision ID: 61228cc80f4f
Revises: f05021a3c1cf
Create Date: 2026-03-05 23:13:24.565465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '61228cc80f4f'
down_revision: Union[str, Sequence[str], None] = 'f05021a3c1cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar updated_by y liquidated_at a la tabla sales."""
    op.add_column('sales', sa.Column('updated_by', sa.UUID(), nullable=True, comment='User who last edited the sale'))
    op.add_column('sales', sa.Column('liquidated_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when the sale was liquidated/collected'))
    op.create_foreign_key('fk_sales_updated_by_users', 'sales', 'users', ['updated_by'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Revertir updated_by y liquidated_at de la tabla sales."""
    op.drop_constraint('fk_sales_updated_by_users', 'sales', type_='foreignkey')
    op.drop_column('sales', 'liquidated_at')
    op.drop_column('sales', 'updated_by')

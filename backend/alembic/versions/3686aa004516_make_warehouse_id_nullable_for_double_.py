"""make_warehouse_id_nullable_for_double_entry

Revision ID: 3686aa004516
Revises: f8ef89451aa6
Create Date: 2026-02-01 21:02:08.814195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3686aa004516'
down_revision: Union[str, Sequence[str], None] = 'f8ef89451aa6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Make warehouse_id nullable in purchase_lines table
    # This allows double-entry purchase lines to have NULL warehouse_id (no physical inventory movement)
    op.alter_column('purchase_lines', 'warehouse_id',
                    existing_type=sa.UUID(),
                    nullable=True)
    
    # Make warehouse_id nullable in sales table
    # This allows double-entry sales to have NULL warehouse_id (no physical inventory movement)
    op.alter_column('sales', 'warehouse_id',
                    existing_type=sa.UUID(),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Note: This will fail if there are existing NULL values
    # In production, you should first update NULL values to a valid warehouse_id
    op.alter_column('sales', 'warehouse_id',
                    existing_type=sa.UUID(),
                    nullable=False)
    
    op.alter_column('purchase_lines', 'warehouse_id',
                    existing_type=sa.UUID(),
                    nullable=False)

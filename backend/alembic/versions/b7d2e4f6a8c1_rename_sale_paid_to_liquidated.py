"""rename sale status paid to liquidated and add cancelled audit fields

Revision ID: b7d2e4f6a8c1
Revises: a5f4ebedb73e
Create Date: 2026-03-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7d2e4f6a8c1'
down_revision: Union[str, Sequence[str], None] = 'a5f4ebedb73e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Renombrar status 'paid' a 'liquidated' y agregar campos cancelled_at/by."""
    # Renombrar valor del enum sale_status
    op.execute("ALTER TYPE sale_status RENAME VALUE 'paid' TO 'liquidated'")

    # Agregar campos de auditoria para cancelacion
    op.add_column('sales', sa.Column('cancelled_by', sa.Uuid(), nullable=True))
    op.add_column('sales', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_sales_cancelled_by',
        'sales', 'users',
        ['cancelled_by'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Revertir: renombrar 'liquidated' a 'paid' y eliminar campos cancelled."""
    op.drop_constraint('fk_sales_cancelled_by', 'sales', type_='foreignkey')
    op.drop_column('sales', 'cancelled_at')
    op.drop_column('sales', 'cancelled_by')
    op.execute("ALTER TYPE sale_status RENAME VALUE 'liquidated' TO 'paid'")

"""money_movements account_id nullable for provision_expense

Revision ID: ae239f97fcb5
Revises: c4a1b2d3e5f6
Create Date: 2026-03-09 18:03:52.790437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ae239f97fcb5'
down_revision: Union[str, Sequence[str], None] = 'c4a1b2d3e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Hacer account_id nullable para soportar provision_expense (sin cuenta)."""
    op.alter_column('money_movements', 'account_id',
               existing_type=sa.UUID(),
               nullable=True)


def downgrade() -> None:
    """Revertir account_id a NOT NULL."""
    op.alter_column('money_movements', 'account_id',
               existing_type=sa.UUID(),
               nullable=False)

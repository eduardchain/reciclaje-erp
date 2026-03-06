"""add liquidated_at to purchases

Revision ID: 556bd0161f76
Revises: b2c3d4e5f6a7
Create Date: 2026-03-05 22:17:36.435630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '556bd0161f76'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('purchases', sa.Column('liquidated_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when the purchase was liquidated/paid'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('purchases', 'liquidated_at')

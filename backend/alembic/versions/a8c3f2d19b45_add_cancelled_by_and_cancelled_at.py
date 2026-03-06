"""add cancelled_by and cancelled_at to purchases

Revision ID: a8c3f2d19b45
Revises: 47737646faaf
Create Date: 2026-03-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a8c3f2d19b45'
down_revision: Union[str, Sequence[str], None] = '47737646faaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('purchases', sa.Column('cancelled_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.add_column('purchases', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('purchases', 'cancelled_at')
    op.drop_column('purchases', 'cancelled_by')

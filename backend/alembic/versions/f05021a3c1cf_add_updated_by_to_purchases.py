"""add updated_by to purchases

Revision ID: f05021a3c1cf
Revises: 556bd0161f76
Create Date: 2026-03-05 22:58:56.083697

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f05021a3c1cf'
down_revision: Union[str, Sequence[str], None] = '556bd0161f76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('purchases', sa.Column('updated_by', sa.UUID(), nullable=True, comment='User who last edited the purchase'))
    op.create_foreign_key('fk_purchases_updated_by_users', 'purchases', 'users', ['updated_by'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_purchases_updated_by_users', 'purchases', type_='foreignkey')
    op.drop_column('purchases', 'updated_by')

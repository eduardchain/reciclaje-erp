"""rename purchase status paid to liquidated

Revision ID: 47737646faaf
Revises: 61228cc80f4f
Create Date: 2026-03-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '47737646faaf'
down_revision: Union[str, Sequence[str], None] = '61228cc80f4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Renombrar valor del enum purchase_status: 'paid' -> 'liquidated'
    # PostgreSQL soporta ALTER TYPE ... RENAME VALUE desde v10
    op.execute("ALTER TYPE purchase_status RENAME VALUE 'paid' TO 'liquidated'")


def downgrade() -> None:
    op.execute("ALTER TYPE purchase_status RENAME VALUE 'liquidated' TO 'paid'")

"""add_received_quantity_to_sale_lines

Revision ID: bf0ec8815fdc
Revises: 84cf14a916ca
Create Date: 2026-03-11 12:24:02.285656

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf0ec8815fdc'
down_revision: Union[str, Sequence[str], None] = '84cf14a916ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agregar cantidad recibida por cliente a lineas de venta."""
    op.add_column(
        'sale_lines',
        sa.Column(
            'received_quantity',
            sa.Numeric(10, 3),
            nullable=True,
            comment='Cantidad recibida por el cliente (puede diferir de quantity)',
        ),
    )


def downgrade() -> None:
    """Eliminar columna received_quantity."""
    op.drop_column('sale_lines', 'received_quantity')

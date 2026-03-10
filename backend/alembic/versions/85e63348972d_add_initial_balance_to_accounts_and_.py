"""add_initial_balance_to_accounts_and_third_parties

Revision ID: a1b2c3d4e5f6
Revises: 22f663ae5d63
Create Date: 2026-03-10 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85e63348972d'
down_revision: str = '22f663ae5d63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar initial_balance a money_accounts
    op.add_column('money_accounts', sa.Column(
        'initial_balance', sa.Numeric(precision=15, scale=2),
        nullable=False, server_default='0',
    ))
    # Datos existentes: initial_balance = 0 (server_default).
    # Todos los cambios de saldo ya estan rastreados como operaciones.

    # Agregar initial_balance a third_parties
    op.add_column('third_parties', sa.Column(
        'initial_balance', sa.Numeric(precision=15, scale=2),
        nullable=False, server_default='0',
    ))
    # Datos existentes: initial_balance = 0 (server_default).


def downgrade() -> None:
    op.drop_column('third_parties', 'initial_balance')
    op.drop_column('money_accounts', 'initial_balance')

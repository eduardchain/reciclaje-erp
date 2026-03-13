"""double_entry_2step_workflow

Revision ID: d29c1bc28dcb
Revises: d3e73695da43
Create Date: 2026-03-12 21:10:21.210959

Agrega flujo de 2 pasos (registrar → liquidar) a doble partida.
Nuevas columnas audit + migrar status 'completed' → 'liquidated'.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd29c1bc28dcb'
down_revision: Union[str, Sequence[str], None] = 'd3e73695da43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nuevas columnas audit en double_entries
    op.add_column('double_entries', sa.Column('created_by', sa.Uuid(), nullable=True))
    op.add_column('double_entries', sa.Column('liquidated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('double_entries', sa.Column('liquidated_by', sa.Uuid(), nullable=True))
    op.add_column('double_entries', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('double_entries', sa.Column('cancelled_by', sa.Uuid(), nullable=True))

    op.create_foreign_key('fk_de_created_by', 'double_entries', 'users', ['created_by'], ['id'])
    op.create_foreign_key('fk_de_liquidated_by', 'double_entries', 'users', ['liquidated_by'], ['id'])
    op.create_foreign_key('fk_de_cancelled_by', 'double_entries', 'users', ['cancelled_by'], ['id'])

    # Migrar status: completed → liquidated (con audit timestamps)
    op.execute("""
        UPDATE double_entries
        SET status = 'liquidated',
            liquidated_at = created_at
        WHERE status = 'completed'
    """)


def downgrade() -> None:
    # Revertir status
    op.execute("UPDATE double_entries SET status = 'completed' WHERE status = 'liquidated'")

    op.drop_constraint('fk_de_cancelled_by', 'double_entries', type_='foreignkey')
    op.drop_constraint('fk_de_liquidated_by', 'double_entries', type_='foreignkey')
    op.drop_constraint('fk_de_created_by', 'double_entries', type_='foreignkey')

    op.drop_column('double_entries', 'cancelled_by')
    op.drop_column('double_entries', 'cancelled_at')
    op.drop_column('double_entries', 'liquidated_by')
    op.drop_column('double_entries', 'liquidated_at')
    op.drop_column('double_entries', 'created_by')

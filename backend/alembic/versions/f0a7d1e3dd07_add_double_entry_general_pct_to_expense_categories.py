"""add double_entry_general_pct to expense_categories

% de los gastos GENERALES de una categoria atribuido a la UN sistema
Pasa Mano (plan A.2). Default 0 = comportamiento actual intacto (no se
atribuye nada hasta que el cliente configure porcentajes). Sin backfill.

Revision ID: f0a7d1e3dd07
Revises: 120ca61fa631
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f0a7d1e3dd07"
down_revision = "120ca61fa631"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expense_categories",
        sa.Column(
            "double_entry_general_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
            comment=(
                "% de los gastos GENERALES de esta categoria atribuido a la UN sistema "
                "Pasa Mano (0-100). Solo categorias raiz indirectas; hijas heredan en lectura."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("expense_categories", "double_entry_general_pct")

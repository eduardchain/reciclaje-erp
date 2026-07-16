"""P&L por rubros: pnl_section en categorias de gasto (plan pnl-por-rubros)

Revision ID: a4317e2cd050
Revises: c45cbce9f391
Create Date: 2026-07-15

Columna configurable por categoria RAIZ (hijas heredan en lectura, patron #59):
operativo (default) | financiero. La seccion Depreciacion NO se configura aca —
la asigna automaticamente el source_type depreciation_expense en el P&L.
server_default='operativo' -> cero backfill, el P&L historico no cambia.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a4317e2cd050"
down_revision = "c45cbce9f391"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expense_categories",
        sa.Column(
            "pnl_section",
            sa.String(20),
            nullable=False,
            server_default="operativo",
        ),
    )


def downgrade() -> None:
    op.drop_column("expense_categories", "pnl_section")

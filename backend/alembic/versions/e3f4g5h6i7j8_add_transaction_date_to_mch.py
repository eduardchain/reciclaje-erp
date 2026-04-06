"""Add transaction_date to material_cost_histories

Revision ID: e3f4g5h6i7j8
Revises: d2e3f4g5h6i7
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f4g5h6i7j8"
down_revision = "d2e3f4g5h6i7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "material_cost_histories",
        sa.Column("transaction_date", sa.Date(), nullable=True),
    )

    # Backfill desde fuentes
    op.execute("""
        UPDATE material_cost_histories mch
        SET transaction_date = p.date::date
        FROM purchases p
        WHERE mch.source_type = 'purchase_liquidation' AND mch.source_id = p.id
    """)
    op.execute("""
        UPDATE material_cost_histories mch
        SET transaction_date = ia.date::date
        FROM inventory_adjustments ia
        WHERE mch.source_type = 'adjustment_increase' AND mch.source_id = ia.id
    """)
    op.execute("""
        UPDATE material_cost_histories mch
        SET transaction_date = mt.date::date
        FROM material_transformations mt
        WHERE mch.source_type IN ('transformation_in', 'transformation_out')
          AND mch.source_id = mt.id
    """)

    # Fallback: registros sin match usan created_at
    op.execute("""
        UPDATE material_cost_histories
        SET transaction_date = created_at::date
        WHERE transaction_date IS NULL
    """)


def downgrade():
    op.drop_column("material_cost_histories", "transaction_date")

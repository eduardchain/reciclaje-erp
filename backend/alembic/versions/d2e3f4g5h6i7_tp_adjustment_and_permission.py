"""Add tp_adjustment column and permission

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4g5h6
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = "d2e3f4g5h6i7"
down_revision = "c1d2e3f4g5h6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add adjustment_class column
    op.add_column("money_movements", sa.Column("adjustment_class", sa.String(10), nullable=True))

    # Add permission
    conn = op.get_bind()
    conn.execute(text("""
        INSERT INTO permissions (id, code, display_name, module, description, sort_order)
        VALUES (gen_random_uuid(), 'treasury.adjust_balances', 'Ajustar Saldos de Terceros', 'treasury', 'Permite ajustar saldos de terceros (perdida/ganancia)', 68)
        ON CONFLICT (code) DO NOTHING
    """))

    # Assign to admin and liquidador
    for role_name in ("admin", "liquidador"):
        conn.execute(text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE r.name = :role_name AND r.is_system_role = true
              AND p.code = 'treasury.adjust_balances'
              AND NOT EXISTS (
                SELECT 1 FROM role_permissions rp
                WHERE rp.role_id = r.id AND rp.permission_id = p.id
              )
        """), {"role_name": role_name})


def downgrade() -> None:
    op.drop_column("money_movements", "adjustment_class")
    conn = op.get_bind()
    conn.execute(text("""
        DELETE FROM role_permissions WHERE permission_id = (
            SELECT id FROM permissions WHERE code = 'treasury.adjust_balances'
        )
    """))
    conn.execute(text("DELETE FROM permissions WHERE code = 'treasury.adjust_balances'"))

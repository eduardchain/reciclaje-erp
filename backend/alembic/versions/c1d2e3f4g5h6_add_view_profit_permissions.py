"""Add view_profit permissions for sales and double_entries

Revision ID: c1d2e3f4g5h6
Revises: b4c5d6e7f8a9
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = "c1d2e3f4g5h6"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Insert new permissions
    conn.execute(text("""
        INSERT INTO permissions (id, code, display_name, module, description, sort_order)
        VALUES
            (gen_random_uuid(), 'sales.view_profit', 'Ver Utilidad en Ventas', 'sales', 'Permite ver utilidad bruta y neta en ventas', 17),
            (gen_random_uuid(), 'double_entries.view_profit', 'Ver Utilidad en Doble Partida', 'double_entries', 'Permite ver utilidad y margen en doble partida', 26)
        ON CONFLICT (code) DO NOTHING
    """))

    # Assign to system roles: liquidador, viewer, admin
    for role_name in ("liquidador", "viewer", "admin"):
        for perm_code in ("sales.view_profit", "double_entries.view_profit"):
            conn.execute(text("""
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r, permissions p
                WHERE r.name = :role_name AND r.is_system_role = true
                  AND p.code = :perm_code
                  AND NOT EXISTS (
                    SELECT 1 FROM role_permissions rp
                    WHERE rp.role_id = r.id AND rp.permission_id = p.id
                  )
            """), {"role_name": role_name, "perm_code": perm_code})


def downgrade() -> None:
    conn = op.get_bind()
    for code in ("sales.view_profit", "double_entries.view_profit"):
        conn.execute(text("""
            DELETE FROM role_permissions WHERE permission_id = (
                SELECT id FROM permissions WHERE code = :code
            )
        """), {"code": code})
        conn.execute(text("DELETE FROM permissions WHERE code = :code"), {"code": code})

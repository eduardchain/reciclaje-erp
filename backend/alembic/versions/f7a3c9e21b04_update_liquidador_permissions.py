"""Agregar permisos faltantes al rol liquidador

Revision ID: f7a3c9e21b04
Revises: bbed048158b2
Create Date: 2026-03-13

"""
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f7a3c9e21b04"
down_revision: Union[str, None] = "bbed048158b2"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Agregar purchases.cancel, sales.cancel, reports.view al liquidador."""
    conn = op.get_bind()

    # Obtener IDs de los permisos a agregar
    new_perm_codes = ["purchases.cancel", "sales.cancel", "reports.view"]
    perms = conn.execute(
        sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_perm_codes},
    ).fetchall()
    perm_map = {row[1]: row[0] for row in perms}

    # Obtener todos los roles liquidador del sistema
    liquidador_roles = conn.execute(
        sa.text(
            "SELECT id FROM roles WHERE name = 'liquidador' AND is_system_role = true"
        )
    ).fetchall()

    # Insertar permisos faltantes
    for role_row in liquidador_roles:
        role_id = role_row[0]
        for code in new_perm_codes:
            if code in perm_map:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                    ),
                    {"role_id": role_id, "perm_id": perm_map[code]},
                )


def downgrade() -> None:
    """Quitar permisos agregados al liquidador."""
    conn = op.get_bind()

    perm_codes = ["purchases.cancel", "sales.cancel", "reports.view"]
    perms = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)"),
        {"codes": perm_codes},
    ).fetchall()
    perm_ids = [row[0] for row in perms]

    liquidador_roles = conn.execute(
        sa.text(
            "SELECT id FROM roles WHERE name = 'liquidador' AND is_system_role = true"
        )
    ).fetchall()

    for role_row in liquidador_roles:
        conn.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE role_id = :role_id AND permission_id = ANY(:perm_ids)"
            ),
            {"role_id": role_row[0], "perm_ids": perm_ids},
        )

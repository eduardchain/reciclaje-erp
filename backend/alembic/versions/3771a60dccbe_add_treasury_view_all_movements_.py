"""Agregar permiso treasury.view_all_movements

Sin este permiso, los usuarios con treasury.view_movements solo ven
los movimientos que ellos mismos crearon (created_by = su user_id).
Con este permiso ven todos, incluyendo los de created_by=NULL (automáticos).

Roles que reciben el permiso: admin, liquidador.
Roles que NO lo reciben: bascula, viewer (ven solo sus propios movimientos).

Revision ID: 3771a60dccbe
Revises: e3f4g5h6i7j8
Create Date: 2026-04-14

"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "3771a60dccbe"
down_revision: Union[str, None] = "e3f4g5h6i7j8"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

PERMISSION_CODE = "treasury.view_all_movements"
ROLES_WITH_PERMISSION = ["admin", "liquidador"]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Insertar permiso si no existe
    existing = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = :code"),
        {"code": PERMISSION_CODE},
    ).fetchone()

    if not existing:
        perm_id = str(uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
                "VALUES (:id, :code, :display_name, :module, :description, :sort_order)"
            ),
            {
                "id": perm_id,
                "code": PERMISSION_CODE,
                "display_name": "Ver Todos los Movimientos",
                "module": "treasury",
                "description": (
                    "Permite ver todos los movimientos, incluidos los de otros usuarios. "
                    "Sin este permiso, solo se ven los movimientos propios."
                ),
                "sort_order": 83,
            },
        )
    else:
        perm_id = existing[0]

    # 2. Asignar a los roles de sistema correspondientes (en todas las orgs)
    for role_name in ROLES_WITH_PERMISSION:
        roles = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name AND is_system_role = true"),
            {"name": role_name},
        ).fetchall()
        for role_row in roles:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                ),
                {"role_id": role_row[0], "perm_id": perm_id},
            )


def downgrade() -> None:
    conn = op.get_bind()

    perm = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = :code"),
        {"code": PERMISSION_CODE},
    ).fetchone()

    if perm:
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {"pid": perm[0]},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"),
            {"pid": perm[0]},
        )

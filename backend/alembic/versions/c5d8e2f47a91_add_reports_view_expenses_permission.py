"""Agregar permiso reports.view_expenses

Revision ID: c5d8e2f47a91
Revises: 3771a60dccbe
Create Date: 2026-05-07

"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "c5d8e2f47a91"
down_revision: Union[str, None] = "3771a60dccbe"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


PERM_CODE = "reports.view_expenses"
PERM_DISPLAY = "Ver Reporte de Gastos"
PERM_MODULE = "reports"
PERM_DESCRIPTION = "Permite ver el reporte de gastos por UN/Categoria"
PERM_SORT_ORDER = 100

# Roles que reciben el permiso. Admin recibe TODOS los permisos al crearse la org;
# para orgs existentes hay que asignar explicitamente al agregar un permiso nuevo.
ROLES_TO_GRANT = ["admin", "viewer", "liquidador"]


def upgrade() -> None:
    """Insertar permiso reports.view_expenses y asignar a viewer + liquidador."""
    conn = op.get_bind()

    # 1. Insertar permiso si no existe
    existing = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = :code"),
        {"code": PERM_CODE},
    ).fetchone()

    if existing:
        perm_id = existing[0]
    else:
        perm_id = str(uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
                "VALUES (:id, :code, :display_name, :module, :description, :sort_order)"
            ),
            {
                "id": perm_id,
                "code": PERM_CODE,
                "display_name": PERM_DISPLAY,
                "module": PERM_MODULE,
                "description": PERM_DESCRIPTION,
                "sort_order": PERM_SORT_ORDER,
            },
        )

    # 2. Asignar a roles del sistema (viewer + liquidador) en todas las orgs
    role_rows = conn.execute(
        sa.text(
            "SELECT id FROM roles WHERE name = ANY(:names) AND is_system_role = true"
        ),
        {"names": ROLES_TO_GRANT},
    ).fetchall()

    for (role_id,) in role_rows:
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
            ),
            {"role_id": role_id, "perm_id": perm_id},
        )


def downgrade() -> None:
    """Quitar permiso reports.view_expenses."""
    conn = op.get_bind()

    perm = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = :code"),
        {"code": PERM_CODE},
    ).fetchone()

    if perm:
        perm_id = perm[0]
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :perm_id"),
            {"perm_id": perm_id},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = :perm_id"),
            {"perm_id": perm_id},
        )

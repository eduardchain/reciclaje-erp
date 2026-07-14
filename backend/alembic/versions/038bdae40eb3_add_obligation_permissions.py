"""Permisos RBAC de obligaciones financieras (plan F)

- treasury.view_obligations: granular de lectura (patron view_provisions —
  tesoreria no tiene master, solo granulares desde d6e7f8a9b0c1).
- treasury.manage_obligations: crear obligaciones, causar, pagar, anular.

Asignacion a roles sistema existentes: viewer → view; liquidador → view+manage.
Admin bypassa todo (no necesita filas). Los permisos se leen de la tabla
permissions en BD — sin esta migracion el modulo es invisible.

Revision ID: 038bdae40eb3
Revises: 0afbde607a68
Create Date: 2026-07-10
"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "038bdae40eb3"
down_revision: Union[str, None] = "0afbde607a68"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

NEW_PERMISSIONS = [
    ("treasury.view_obligations", "Ver Obligaciones Financieras", "treasury",
     "Permite ver obligaciones financieras (prestamos por pagar/cobrar)", 94),
    ("treasury.manage_obligations", "Gestionar Obligaciones Financieras", "treasury",
     "Permite crear obligaciones, causar intereses, registrar pagos y anular", 95),
]

# rol sistema -> permisos que recibe
ROLE_ASSIGNMENTS = {
    "viewer": ["treasury.view_obligations"],
    "liquidador": ["treasury.view_obligations", "treasury.manage_obligations"],
}


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Insertar permisos que no existan
    new_codes = [p[0] for p in NEW_PERMISSIONS]
    existing = conn.execute(
        sa.text("SELECT code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_codes},
    ).fetchall()
    existing_codes = {row[0] for row in existing}

    for code, display_name, module, description, sort_order in NEW_PERMISSIONS:
        if code not in existing_codes:
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
                    "VALUES (:id, :code, :display_name, :module, :description, :sort_order)"
                ),
                {
                    "id": str(uuid4()),
                    "code": code,
                    "display_name": display_name,
                    "module": module,
                    "description": description,
                    "sort_order": sort_order,
                },
            )

    # 2. Mapear codigo -> id
    perms = conn.execute(
        sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_codes},
    ).fetchall()
    perm_map = {row[1]: row[0] for row in perms}

    # 3. Asignar a roles sistema existentes de todas las orgs
    for role_name, codes in ROLE_ASSIGNMENTS.items():
        roles = conn.execute(
            sa.text(
                "SELECT id FROM roles WHERE name = :name AND is_system_role = true"
            ),
            {"name": role_name},
        ).fetchall()
        for role_row in roles:
            for code in codes:
                if code in perm_map:
                    conn.execute(
                        sa.text(
                            "INSERT INTO role_permissions (role_id, permission_id) "
                            "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                        ),
                        {"role_id": role_row[0], "perm_id": perm_map[code]},
                    )


def downgrade() -> None:
    conn = op.get_bind()
    codes = [p[0] for p in NEW_PERMISSIONS]

    perms = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)"),
        {"codes": codes},
    ).fetchall()
    perm_ids = [row[0] for row in perms]

    if perm_ids:
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = ANY(:perm_ids)"),
            {"perm_ids": perm_ids},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = ANY(:perm_ids)"),
            {"perm_ids": perm_ids},
        )

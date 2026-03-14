"""Agregar permisos edit_prices para compras y ventas

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-03-13

"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

NEW_PERMISSIONS = [
    ("purchases.edit_prices", "Editar Precios en Compras", "purchases", "Permite ingresar y modificar precios al crear/editar", 7),
    ("sales.edit_prices", "Editar Precios en Ventas", "sales", "Permite ingresar y modificar precios al crear/editar", 16),
]


def upgrade() -> None:
    """Insertar permisos edit_prices y asignar a liquidador."""
    conn = op.get_bind()

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

    # Obtener IDs
    perms = conn.execute(
        sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_codes},
    ).fetchall()
    perm_map = {row[1]: row[0] for row in perms}

    # Asignar a liquidador (necesita editar precios al liquidar)
    liquidador_roles = conn.execute(
        sa.text(
            "SELECT id FROM roles WHERE name = 'liquidador' AND is_system_role = true"
        )
    ).fetchall()

    for role_row in liquidador_roles:
        for code in new_codes:
            if code in perm_map:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                    ),
                    {"role_id": role_row[0], "perm_id": perm_map[code]},
                )


def downgrade() -> None:
    """Quitar permisos edit_prices."""
    conn = op.get_bind()

    codes = [p[0] for p in NEW_PERMISSIONS]
    perms = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)"),
        {"codes": codes},
    ).fetchall()
    perm_ids = [row[0] for row in perms]

    if perm_ids:
        conn.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id = ANY(:perm_ids)"
            ),
            {"perm_ids": perm_ids},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = ANY(:perm_ids)"),
            {"perm_ids": perm_ids},
        )

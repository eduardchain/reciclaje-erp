"""Reagrupar permisos de configuracion bajo modulo config + agregar unidades de negocio

Revision ID: b3c4d5e6f7a8
Revises: e7f8a9b0c1d2
Create Date: 2026-03-13

"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

# Permisos existentes que se mueven al modulo "config"
MOVE_TO_CONFIG = [
    "warehouses.view",
    "warehouses.create",
    "warehouses.edit",
    "treasury.manage_accounts",
    "treasury.manage_expenses",
    "materials.view_prices",
    "materials.edit_prices",
]

# Nuevos permisos para unidades de negocio
NEW_PERMISSIONS = [
    ("config.view_business_units", "Ver Unidades de Negocio", "config", "Permite ver unidades de negocio", 124),
    ("config.manage_business_units", "Gestionar Unidades de Negocio", "config", "Permite crear/editar unidades de negocio", 125),
]


def upgrade() -> None:
    """Mover permisos a modulo config y agregar unidades de negocio."""
    conn = op.get_bind()

    # 1. Actualizar modulo de permisos existentes a "config"
    conn.execute(
        sa.text(
            "UPDATE permissions SET module = 'config' WHERE code = ANY(:codes)"
        ),
        {"codes": MOVE_TO_CONFIG},
    )

    # 2. Actualizar sort_order de los permisos movidos
    sort_orders = {
        "warehouses.view": 120,
        "warehouses.create": 121,
        "warehouses.edit": 122,
        "treasury.manage_accounts": 123,
        "treasury.manage_expenses": 126,
        "materials.view_prices": 127,
        "materials.edit_prices": 128,
    }
    for code, sort_order in sort_orders.items():
        conn.execute(
            sa.text(
                "UPDATE permissions SET sort_order = :sort_order WHERE code = :code"
            ),
            {"sort_order": sort_order, "code": code},
        )

    # 3. Insertar nuevos permisos de unidades de negocio
    existing = conn.execute(
        sa.text("SELECT code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": [p[0] for p in NEW_PERMISSIONS]},
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

    # 4. Asignar config.view_business_units a viewer y bascula de cada org
    new_codes = [p[0] for p in NEW_PERMISSIONS]
    perms = conn.execute(
        sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_codes},
    ).fetchall()
    perm_map = {row[1]: row[0] for row in perms}

    # Viewer: ambos permisos (ver)
    viewer_perm_id = perm_map.get("config.view_business_units")
    if viewer_perm_id:
        viewer_roles = conn.execute(
            sa.text(
                "SELECT id FROM roles WHERE name = 'viewer' AND is_system_role = true"
            )
        ).fetchall()
        for role_row in viewer_roles:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                ),
                {"role_id": role_row[0], "perm_id": viewer_perm_id},
            )

    # Bascula: config.view_business_units
    if viewer_perm_id:
        bascula_roles = conn.execute(
            sa.text(
                "SELECT id FROM roles WHERE name = 'bascula' AND is_system_role = true"
            )
        ).fetchall()
        for role_row in bascula_roles:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                ),
                {"role_id": role_row[0], "perm_id": viewer_perm_id},
            )


def downgrade() -> None:
    """Revertir: mover permisos de vuelta y eliminar unidades de negocio."""
    conn = op.get_bind()

    # Restaurar modulos originales
    original_modules = {
        "warehouses.view": ("warehouses", 70),
        "warehouses.create": ("warehouses", 71),
        "warehouses.edit": ("warehouses", 72),
        "treasury.manage_accounts": ("treasury", 83),
        "treasury.manage_expenses": ("treasury", 84),
        "materials.view_prices": ("materials", 44),
        "materials.edit_prices": ("materials", 45),
    }
    for code, (module, sort_order) in original_modules.items():
        conn.execute(
            sa.text(
                "UPDATE permissions SET module = :module, sort_order = :sort_order WHERE code = :code"
            ),
            {"module": module, "sort_order": sort_order, "code": code},
        )

    # Eliminar permisos de unidades de negocio
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

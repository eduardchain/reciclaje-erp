"""Reemplazar treasury.view con permisos granulares dashboard/movements/accounts

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-03-13

"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

NEW_PERMISSIONS = [
    ("treasury.view_dashboard", "Ver Dashboard Tesoreria", "treasury", "Permite ver dashboard de tesoreria", 80),
    ("treasury.view_movements", "Ver Movimientos", "treasury", "Permite ver movimientos de dinero", 81),
    ("treasury.view_accounts", "Ver Cuentas", "treasury", "Permite ver movimientos por cuenta", 82),
]


def upgrade() -> None:
    """Reemplazar treasury.view con 3 permisos granulares y renombrar view_statements."""
    conn = op.get_bind()

    # 1. Crear los 3 nuevos permisos
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

    # 2. Copiar asignaciones de treasury.view a los 3 nuevos permisos
    old_perm = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = 'treasury.view'")
    ).fetchone()

    if old_perm:
        new_perms = conn.execute(
            sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)"),
            {"codes": new_codes},
        ).fetchall()
        new_perm_ids = {row[1]: row[0] for row in new_perms}

        # Obtener roles que tenian treasury.view
        role_ids = conn.execute(
            sa.text("SELECT role_id FROM role_permissions WHERE permission_id = :pid"),
            {"pid": old_perm[0]},
        ).fetchall()

        for role_row in role_ids:
            for code in new_codes:
                if code in new_perm_ids:
                    conn.execute(
                        sa.text(
                            "INSERT INTO role_permissions (role_id, permission_id) "
                            "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                        ),
                        {"role_id": role_row[0], "perm_id": new_perm_ids[code]},
                    )

        # 3. Eliminar treasury.view
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {"pid": old_perm[0]},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"),
            {"pid": old_perm[0]},
        )

    # 4. Renombrar treasury.view_statements display name
    conn.execute(
        sa.text(
            "UPDATE permissions SET display_name = 'Ver Terceros' "
            "WHERE code = 'treasury.view_statements'"
        )
    )


def downgrade() -> None:
    """Restaurar treasury.view y eliminar los 3 granulares."""
    conn = op.get_bind()

    # Recrear treasury.view
    old_id = str(uuid4())
    conn.execute(
        sa.text(
            "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
            "VALUES (:id, 'treasury.view', 'Ver Tesoreria Completa', 'treasury', "
            "'Permite ver todas las cuentas y movimientos', 80) "
            "ON CONFLICT (code) DO NOTHING"
        ),
        {"id": old_id},
    )

    # Restaurar display name
    conn.execute(
        sa.text(
            "UPDATE permissions SET display_name = 'Ver Estados de Cuenta' "
            "WHERE code = 'treasury.view_statements'"
        )
    )

    # Eliminar los 3 nuevos
    new_codes = [p[0] for p in NEW_PERMISSIONS]
    perms = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_codes},
    ).fetchall()
    perm_ids = [row[0] for row in perms]

    if perm_ids:
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = ANY(:pids)"),
            {"pids": perm_ids},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = ANY(:pids)"),
            {"pids": perm_ids},
        )

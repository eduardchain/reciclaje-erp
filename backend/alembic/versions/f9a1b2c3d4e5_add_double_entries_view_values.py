"""Agregar permiso double_entries.view_values

Revision ID: f9a1b2c3d4e5
Revises: 358ce4dce01f
Create Date: 2026-03-17

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = 'f9a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = '358ce4dce01f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION_ID = str(uuid4())


def upgrade() -> None:
    """Agregar permiso double_entries.view_values y asignarlo a admin, liquidador y viewer."""
    # 1. Insertar permiso
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
            "VALUES (:id, 'double_entries.view_values', 'Ver Valores en Doble Partida', 'double_entries', "
            "'Permite ver utilidades y margenes', 25)"
        ).bindparams(id=PERMISSION_ID)
    )

    # 2. Asignar a roles admin, liquidador y viewer (system roles)
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, :perm_id FROM roles r "
            "WHERE r.is_system_role = true AND r.name IN ('admin', 'liquidador', 'viewer')"
        ).bindparams(perm_id=PERMISSION_ID)
    )


def downgrade() -> None:
    """Eliminar permiso double_entries.view_values."""
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id = "
            "(SELECT id FROM permissions WHERE code = 'double_entries.view_values')"
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code = 'double_entries.view_values'")
    )

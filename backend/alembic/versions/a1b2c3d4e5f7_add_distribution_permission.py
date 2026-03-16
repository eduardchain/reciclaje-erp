"""Agregar permiso treasury.manage_distributions

Revision ID: a1b2c3d4e5f7
Revises: d6d507c083c7
Create Date: 2026-03-15

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'd6d507c083c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION_ID = str(uuid4())


def upgrade() -> None:
    """Agregar permiso treasury.manage_distributions y asignarlo a admin y liquidador."""
    # 1. Insertar permiso
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
            "VALUES (:id, 'treasury.manage_distributions', 'Gestionar Reparticiones', 'treasury', "
            "'Permite ver y crear reparticiones de utilidades', 91)"
        ).bindparams(id=PERMISSION_ID)
    )

    # 2. Asignar a roles admin y liquidador (system roles)
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, :perm_id FROM roles r "
            "WHERE r.is_system_role = true AND r.name IN ('admin', 'liquidador')"
        ).bindparams(perm_id=PERMISSION_ID)
    )


def downgrade() -> None:
    """Eliminar permiso treasury.manage_distributions."""
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id = "
            "(SELECT id FROM permissions WHERE code = 'treasury.manage_distributions')"
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code = 'treasury.manage_distributions'")
    )

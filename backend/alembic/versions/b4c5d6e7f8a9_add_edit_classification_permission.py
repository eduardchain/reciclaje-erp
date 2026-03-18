"""Agregar permiso treasury.edit_classification

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-03-18

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION_ID = str(uuid4())


def upgrade() -> None:
    """Agregar permiso treasury.edit_classification y asignarlo a admin y liquidador."""
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
            "VALUES (:id, 'treasury.edit_classification', 'Editar Clasificacion Gastos', 'treasury', "
            "'Editar categoria y UN en movimientos de gasto', 92)"
        ).bindparams(id=PERMISSION_ID)
    )

    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, :perm_id FROM roles r "
            "WHERE r.is_system_role = true AND r.name IN ('admin', 'liquidador')"
        ).bindparams(perm_id=PERMISSION_ID)
    )


def downgrade() -> None:
    """Eliminar permiso treasury.edit_classification."""
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id = "
            "(SELECT id FROM permissions WHERE code = 'treasury.edit_classification')"
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code = 'treasury.edit_classification'")
    )

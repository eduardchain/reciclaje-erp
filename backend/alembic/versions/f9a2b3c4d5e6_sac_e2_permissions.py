"""SAC E2 Migracion E: 3 permisos kg_ledger (plan-sac-e2-kgledger-inbound.md §3.2, D13)

- kg_ledger.view (master) / kg_ledger.manage / kg_ledger.manage_adjustments
  (modulo kg_ledger, v0.5 §14.1)

SIN bloque de role_assignments (D4-E1): los roles de sistema NO ganan capacidad
— solo admin por bypass; los roles SAC finos llegan en E5. InboundOrder reusa
purchases.* (no siembra permisos propios). Catalogo 84 -> 87.

Dual-write triple: esta migracion + PERMISSIONS_CATALOG + MODULE_DISPLAY_NAMES
en services/role.py.

Revision ID: f9a2b3c4d5e6
Revises: e8f1a2b3c4d5
Create Date: 2026-07-16
"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f9a2b3c4d5e6"
down_revision: Union[str, None] = "e8f1a2b3c4d5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

NEW_PERMISSIONS = [
    ("kg_ledger.view", "Ver Cuentas en Kg", "kg_ledger",
     "Permite ver saldos, movimientos y estados de cuenta del KgLedger", 144),
    ("kg_ledger.manage", "Gestionar Cuentas en Kg", "kg_ledger",
     "Permite crear y editar la metadata de cuentas KgLedger", 145),
    ("kg_ledger.manage_adjustments", "Ajustes Manuales de Kg", "kg_ledger",
     "Permite crear y anular movimientos manuales del KgLedger (auditados)", 146),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Insertar permisos que no existan (idempotente, patron d7e0a3c4b5f6)
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

    # SIN role_assignments (D4-E1): cero cambio de capacidad para usuarios existentes.


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

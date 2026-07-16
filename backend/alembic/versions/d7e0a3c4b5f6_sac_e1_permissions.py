"""SAC E1 Migracion C: 6 permisos nuevos (plan-sac-e1-configuracion.md §3.3, D4/D5)

- tariffs.view / tariffs.manage (modulo tariffs, v0.5 §14.1)
- formulas.view / formulas.manage (modulo formulas, v0.5 §14.1)
- config.view_fleet / config.manage_fleet (modulo config — opcion "config
  generico" que §11.1.14 deja abierta, D5)

SIN bloque de role_assignments (D4): en E1 Johana es admin (bypass) y los
roles SAC finos llegan en E5 — los usuarios de los 3 clientes existentes no
ganan capacidad alguna. Los 9 permisos restantes de §14.1 se siembran con su
entrega (kg_ledger -> E2, maquila/willard -> E3/E4, exceptions/dashboard -> E5).

Dual-write triple (D4): esta migracion + PERMISSIONS_CATALOG +
MODULE_DISPLAY_NAMES en services/role.py.

Revision ID: d7e0a3c4b5f6
Revises: c6d9f2b3a4e5
Create Date: 2026-07-16
"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d7e0a3c4b5f6"
down_revision: Union[str, None] = "c6d9f2b3a4e5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

NEW_PERMISSIONS = [
    ("config.view_fleet", "Ver Conductores y Vehiculos", "config",
     "Permite ver los maestros de conductores y vehiculos", 129),
    ("config.manage_fleet", "Gestionar Conductores y Vehiculos", "config",
     "Permite crear y editar conductores y vehiculos", 130),
    ("tariffs.view", "Ver Tarifas", "tariffs",
     "Permite ver tarifas de servicio (historico y vigente)", 140),
    ("tariffs.manage", "Gestionar Tarifas", "tariffs",
     "Permite crear nuevas tarifas de servicio (append-only)", 141),
    ("formulas.view", "Ver Formulas de Conversion", "formulas",
     "Permite ver formulas de conversion de materiales", 142),
    ("formulas.manage", "Gestionar Formulas de Conversion", "formulas",
     "Permite crear nuevas formulas de conversion (append-only)", 143),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Insertar permisos que no existan (idempotente, patron 038bdae40eb3)
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

    # SIN role_assignments (D4): cero cambio de capacidad para usuarios existentes.


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

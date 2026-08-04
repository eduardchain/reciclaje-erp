"""SAC ajustes 2026-08-03 (C) — permiso config.manage_sac_settings.

Johana pidio poder agregar centros de distribucion Willard sin depender del
superusuario. El obstaculo no es el CRUD sino el guard: organization.settings
es un JSONB con semantica REPLACE donde viven, en el MISMO dict, los 3 feature
flags — un endpoint generico de settings para admins de org seria escalada de
privilegios (podrian encender maquila o traslados). La salida es un endpoint
estrecho que solo puede tocar la clave willard_distribution_centers, y eso
exige su propio permiso.

SIN wiring a SYSTEM_ROLES (politica D4 de E1): viewer/liquidador no ganan
capacidad; en SAC lo tienen los 4 admins por bypass. Los usuarios de las 3
orgs cliente no ganan absolutamente nada — y la unica UI que lo consume esta
ademas tras FlagGate("kg_ledger_enabled"), invisible para ellas.

Dual-write triple: esta migracion + PERMISSIONS_CATALOG + (el modulo `config`
ya existe en MODULE_DISPLAY_NAMES, no hay entrada nueva).

Revision ID: c4d5e6f7a8b9
Revises: d5e6f7a8b9c0
"""
from typing import Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

NEW_PERMISSIONS = [
    ("config.manage_sac_settings", "Gestionar Configuracion SAC", "config",
     "Permite editar los centros de distribucion Willard de la organizacion", 131),
]


def upgrade() -> None:
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

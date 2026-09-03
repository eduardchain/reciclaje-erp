"""W1 — permiso sales.review (revisar salidas a Willard)

La salida certifica pesos antes de liquidar, igual que la Entrada (#93/#95). El
permiso es propio y no reusa `sales.liquidate` porque el punto del paso es la
separacion: quien pesa y certifica no tiene por que poder liquidar la venta.

SIN wiring a SYSTEM_ROLES (politica D4 de E1): viewer/liquidador no ganan nada,
y en SAC lo reciben los admins por bypass. Las 3 orgs cliente no ven diferencia
— el router que lo consume esta ademas tras require_org_flag("kg_ledger_enabled").

Dual-write: esta migracion + PERMISSIONS_CATALOG (el modulo `sales` ya existe).

Revision ID: a5b6c7d8e9f0
Revises: f9a0b1c2d3e4
"""
from typing import Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

NEW_PERMISSIONS = [
    ("sales.review", "Revisar Salidas", "sales",
     "Permite marcar una salida a Willard como revisada (certifica pesos y habilita liquidar, SAC)",
     149),
]


def upgrade() -> None:
    conn = op.get_bind()
    new_codes = [p[0] for p in NEW_PERMISSIONS]
    existing = {
        row[0]
        for row in conn.execute(
            sa.text("SELECT code FROM permissions WHERE code = ANY(:codes)"),
            {"codes": new_codes},
        ).fetchall()
    }
    for code, display_name, module, description, sort_order in NEW_PERMISSIONS:
        if code in existing:
            continue
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


def downgrade() -> None:
    conn = op.get_bind()
    codes = [p[0] for p in NEW_PERMISSIONS]
    conn.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE code = ANY(:codes))"),
        {"codes": codes},
    )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": codes}
    )

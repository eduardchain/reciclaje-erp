"""Retira el permiso muerto `sales.review` del catalogo (#105 item 3)

Nacio con W1 (a5b6c7d8e9f0) para el paso "Revisar" de las salidas, que se
elimino el 2026-09-09 (Hugo, demo 28-ago: "esto funciona muy diferente porque
inmediatamente queda la deuda"). Desde entonces ningun endpoint lo consume y el
seeder ya no lo concede: concedia exactamente nada.

F7 de QA, declarado: el DELETE borra sus asignaciones en `role_permissions`
por `ondelete=CASCADE` EN SILENCIO y el downgrade NO las restaura (solo
reinserta la fila del catalogo). En dev habia 4 asignaciones, todas de orgs
SAC; en Costa/Biogreen/Meta ninguna segun la replica — prod se infiere, no se
verifica. Idempotente: fila ausente -> no-op.

Revision ID: b8c9d0e1f2a4
Revises: a7b8c9d0e1f3
"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a4"
down_revision = "a7b8c9d0e1f3"
branch_labels = None
depends_on = None

CODE = "sales.review"


def upgrade() -> None:
    conn = op.get_bind()
    n_assign = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM role_permissions rp "
            "JOIN permissions p ON p.id = rp.permission_id WHERE p.code = :code"
        ),
        {"code": CODE},
    ).scalar()
    n = conn.execute(
        sa.text("DELETE FROM permissions WHERE code = :code"), {"code": CODE}
    ).rowcount
    print(
        f"[b8c9d0e1f2a4] {CODE}: {n} fila(s) del catalogo borrada(s); "
        f"{n_assign} asignacion(es) en role_permissions cayeron por CASCADE"
    )


def downgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM permissions WHERE code = :code"), {"code": CODE}
    ).first()
    if exists:
        return
    conn.execute(
        sa.text(
            "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
            "VALUES (:id, :code, :display_name, :module, :description, :sort_order)"
        ),
        {
            "id": str(uuid4()),
            "code": CODE,
            "display_name": "Revisar Salidas",
            "module": "sales",
            "description": (
                "Permite marcar una salida a Willard como revisada "
                "(certifica pesos y habilita liquidar, SAC)"
            ),
            "sort_order": 149,
        },
    )

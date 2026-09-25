"""double_entries: unicidad (organization_id, double_entry_number) — D5 del plan de locks

Los otros ocho contadores del sistema ya tienen su indice unico; doble partida
no lo tenia (solo pkey, purchase_id y sale_id). Con la llave del advisory lock
aleatorizada por proceso (defecto A del plan) y produccion en `--workers 4`,
una colision de numero en cruces no daba un 500 como en compras o ventas:
daba DOS cruces con el mismo numero, en silencio.

GATE DE DATOS (patron G1/G2 de #93): si ya existen duplicados, la migracion se
DETIENE con el listado en vez de fallar a medias. `alembic/env.py` corre las
migraciones pendientes en una sola transaccion, asi que un gate que levanta
deja la BD exactamente como estaba; y el skill de deploy encadena
`alembic upgrade head && systemctl restart`, asi que tampoco reinicia el
backend con codigo nuevo sobre esquema viejo. Quien decide como renumerar es
Daniel; despues se re-corre.

Replica de prod al 2026-09-02: cero duplicados en las 3 orgs cliente.

Revision ID: d1e2f3a4b5c6
Revises: b8c9d0e1f2a4
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "b8c9d0e1f2a4"
branch_labels = None
depends_on = None

CONSTRAINT = "uq_double_entries_org_number"


def upgrade() -> None:
    conn = op.get_bind()
    dups = conn.execute(
        sa.text(
            "SELECT organization_id, double_entry_number, COUNT(*) AS n "
            "FROM double_entries GROUP BY organization_id, double_entry_number "
            "HAVING COUNT(*) > 1 ORDER BY organization_id, double_entry_number"
        )
    ).fetchall()
    if dups:
        listado = "\n".join(f"  org={r[0]} numero={r[1]} x{r[2]}" for r in dups)
        raise RuntimeError(
            f"[{revision}] GATE: {len(dups)} numero(s) de doble partida duplicado(s); "
            "no se crea el indice unico hasta renumerarlos (decide Daniel):\n" + listado
        )
    print(f"[{revision}] cero duplicados en double_entries; creando {CONSTRAINT}")
    op.create_unique_constraint(
        CONSTRAINT, "double_entries", ["organization_id", "double_entry_number"]
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "double_entries", type_="unique")

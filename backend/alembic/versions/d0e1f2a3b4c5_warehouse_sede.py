"""SAC — sede de la bodega (warehouses.sede_warehouse_id)

Un traslado dos pasos (#84) emitia kg intersede y maquila por el solo hecho de
que el material tuviera formula, SIN mirar el recorrido. Con eso, mover material
de Circunvalar al Molino —misma sede, "es un solo inventario" (Johana,
2026-08-11)— habria inventado deuda de plomo planta<->circunvalar y un cargo de
maquila por material que nunca salio de la sede.

Esta columna agrupa bodegas en sedes. La regla pasa a ser: kg + maquila SOLO si
el traslado cruza de sede.

🔴 TABLA COMPARTIDA (las 7 orgs) — golden es gate duro.

No-regresion por construccion: NULL = la bodega es su propia sede. Con NULL en
todas —el estado de las 7 orgs al momento de esta migracion— dos bodegas
distintas son siempre dos sedes distintas, asi que todo traslado sigue siendo
intersede y el comportamiento queda byte a byte. Solo cambia donde alguien
agrupe explicitamente.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouses",
        sa.Column(
            "sede_warehouse_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Sede a la que pertenece (NULL = es su propia sede)",
        ),
    )
    op.create_foreign_key(
        None, "warehouses", "warehouses",
        ["sede_warehouse_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_column("warehouses", "sede_warehouse_id")

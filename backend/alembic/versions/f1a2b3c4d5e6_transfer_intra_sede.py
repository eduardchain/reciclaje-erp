"""SAC — traslado intra-sede sin transito (transit_warehouse_id nullable)

Dentro de una misma sede no se pesa al salir ni al llegar (Daniel, 2026-08-11):
el traslado no es un ciclo de despacho/confirmacion, es mover material. Por eso
un traslado intra-sede nace `received`, en UN solo salto origen -> destino, sin
pasar por una bodega de transito.

NULL en `transit_warehouse_id` = el traslado no tuvo transito = fue intra-sede.

`transfers` es tabla EXCLUSIVA SAC (cero filas en las 3 orgs cliente) y no es una
de las 15 capturas del golden — a diferencia de `warehouses` en d0e1f2a3b4c5.

Revision ID: f1a2b3c4d5e6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "transfers", "transit_warehouse_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
        comment="Bodega de transito (NULL = traslado intra-sede, sin transito)",
    )


def downgrade() -> None:
    # Solo revierte si no hay traslados intra-sede: la columna volveria a NOT NULL
    op.execute("DELETE FROM transfers WHERE transit_warehouse_id IS NULL")
    op.alter_column(
        "transfers", "transit_warehouse_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )

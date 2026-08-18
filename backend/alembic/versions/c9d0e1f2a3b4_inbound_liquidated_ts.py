"""SAC #93 — hora real de liquidacion de la Entrada (inbound_orders.liquidated_ts)

Pruebas de usuario 2026-08-11: "por que la liquidacion no tiene hora?".

`Purchase.liquidated_at` es fecha de NEGOCIO (mediodia UTC, #42/#87) — es por
donde cortan todos los reportes y NO lleva hora; pintarla con hora imprimia
"07:00 a. m." en Bogota, el defecto que #87 corrigio. El instante real del clic
no se persistia en ninguna parte.

Esta columna lo guarda SOLO para la Entrada. Va aca y no en purchases/sales/
double_entries (la deuda declarada en #87) porque `inbound_orders` es tabla
EXCLUSIVA de SAC: cero filas en las 3 organizaciones cliente, cero riesgo en el
golden. La deuda de las tablas compartidas sigue abierta.

Aditiva y nullable: las entradas ya liquidadas quedan sin hora (no se inventa).

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inbound_orders",
        sa.Column(
            "liquidated_ts",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Instante real de la liquidacion (auditoria) — NO usar para cortes",
        ),
    )


def downgrade() -> None:
    op.drop_column("inbound_orders", "liquidated_ts")

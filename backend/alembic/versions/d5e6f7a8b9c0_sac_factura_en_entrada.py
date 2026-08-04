"""SAC ajustes 2026-08-03 (A) — factura de la captura en la Entrada.

Johana en la reunion del 3-ago: "faltaria como colocarle el numero de la
factura en caso de que la tenga". Daniel confirmo que aplica a AMBOS tipos.

Fuente unica de verdad POR TIPO (D1 del plan): en tipo compra la factura vive
en purchases.invoice_number (el documento comercial, que el modulo de Compras
ya muestra, busca y exporta) y esta columna queda NULL; en Willard no hay
compra derivada, asi que vive aca. La lectura del response es condicional —
la desincronizacion es imposible por construccion, no algo que haya que
vigilar en tres caminos de escritura.

Aditiva y nullable sobre inbound_orders, tabla EXCLUSIVA de SAC: las 3 orgs
cliente tienen cero filas y el router esta require_org_flag-gated, asi que no
puede aparecer en ninguna captura del golden.

Revision ID: d5e6f7a8b9c0
Revises: a7b8c9d0e1f2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inbound_orders",
        sa.Column(
            "invoice_number",
            sa.String(length=50),
            nullable=True,
            comment=(
                "Factura de recepciones Willard (tipo compra: vive en "
                "purchases.invoice_number)"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("inbound_orders", "invoice_number")

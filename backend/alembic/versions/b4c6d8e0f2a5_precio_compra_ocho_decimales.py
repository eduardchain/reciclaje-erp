"""El valor total digitado llega exacto a la compra: precio con 8 decimales

Johana digito $3.138.450 para 1.503 unidades y la compra nacio en
$3.138.444,36. El unitario se deriva como total/cantidad y se guardaba con 2
decimales, asi que el error del redondeo (hasta medio centavo) se multiplicaba
por la cantidad: hasta cantidad x $0,005. Con 8 decimales queda bajo medio
centavo para cualquier cantidad que admite `purchase_lines.quantity`
(Numeric(10,3)). Plan: docs/planes/plan-redondeo-precio-compras.md v1.1.

Tres columnas pasan de Numeric(15,2) a Numeric(21,8) (13 digitos enteros, los
mismos de antes):

1. `purchase_lines.unit_price` — tabla COMPARTIDA por todas las organizaciones.
2. `inventory_movements.unit_cost` — tabla COMPARTIDA. Va en el MISMO cambio
   porque la reversa de una compra (cancelar, desliquidar una Entrada) saca del
   pool con el costo leido del movimiento (#66 H1): con la linea en 8 y el
   movimiento en 2, la diferencia se esconderia en el promedio o iria al P&L.
3. `inbound_line_allocations.unit_price` — exclusiva de SAC.

Ensanchar la escala NO cambia ningun valor guardado (2088.12 queda
2088.12000000). Reescribe la tabla: segundos con los volumenes de hoy.

⚠️ El downgrade vuelve a Numeric(15,2) y REDONDEA a centavos todo lo que se
haya guardado con mas decimales despues del upgrade. No es reversible sin
perdida.

Revision ID: b4c6d8e0f2a5
Revises: a3b5c7d9e1f2
"""
from alembic import op
import sqlalchemy as sa

revision = "b4c6d8e0f2a5"
down_revision = "a3b5c7d9e1f2"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("purchase_lines", "unit_price"),
    ("inventory_movements", "unit_cost"),
    ("inbound_line_allocations", "unit_price"),
)


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(15, 2),
            type_=sa.Numeric(21, 8),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(21, 8),
            type_=sa.Numeric(15, 2),
            existing_nullable=False,
        )

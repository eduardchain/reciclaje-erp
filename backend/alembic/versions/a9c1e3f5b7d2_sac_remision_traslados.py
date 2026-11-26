"""SAC: remision en los traslados

Plan: docs/planes/plan-sac-remision-traslados.md v1.3 + adenda 1.

`transfers.remission_number` (String(50), NULL): el numero del papel que
acompana el despacho, del MISMO talonario de las Entradas y las Salidas de
control (Q-75). Obligatoria al despachar (la exige el schema, no la BD); los
traslados anteriores a este ciclo quedan en NULL. Tabla exclusiva SAC.

Aditiva pura: una columna nullable, sin default y sin indice (la llave de la
remision se calcula en SQL, como en las otras dos fuentes del talonario).
Downgrade: borra la columna (las remisiones capturadas se pierden).

Revision ID: a9c1e3f5b7d2
Revises: f8a0b2c4d6e9
"""
from alembic import op
import sqlalchemy as sa

revision = "a9c1e3f5b7d2"
down_revision = "f8a0b2c4d6e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transfers",
        sa.Column("remission_number", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transfers", "remission_number")
